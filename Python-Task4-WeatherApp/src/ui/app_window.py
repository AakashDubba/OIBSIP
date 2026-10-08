"""Modern Dark-Mode CustomTkinter Desktop Application for NewsWorld Contextual Weather Engine.

Features:
- Non-blocking multithreaded network I/O: GUI remains 100% responsive.
- Dynamic Celsius/Fahrenheit toggle with instant unit conversion.
- 6-hour hourly trend forecast & 5-day daily outlook.
- Metric cards for temperature, humidity, wind velocity, and feels-like.
- Integrated regional breaking news feed bridge.
- Persistent user preferences (last city, preferred unit).
- Optional IP-based location auto-detection.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

import customtkinter as ctk  # type: ignore[import-untyped]

from src.api.news_bridge import RegionalNewsBridge, RegionalNewsResult
from src.api.weather_client import WeatherClient, WeatherData, WeatherResult
from src.config import UserPreferences, load_preferences, save_preferences

logger = logging.getLogger(__name__)

# Appearance Setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class WeatherAppWindow(ctk.CTk):
    """Main desktop interface for the Contextual Weather Engine."""

    def __init__(
        self,
        weather_client: Optional[WeatherClient] = None,
        news_bridge: Optional[RegionalNewsBridge] = None,
        preferences: Optional[UserPreferences] = None,
    ) -> None:
        super().__init__()

        self.weather_client = weather_client or WeatherClient()
        self.news_bridge = news_bridge or RegionalNewsBridge()
        self.preferences = preferences or load_preferences()

        # Window Configuration
        self.title("NewsWorld Contextual Weather Engine")
        self.geometry("1060x780")
        self.minsize(960, 680)

        # State Variables
        self.current_unit = self.preferences.temperature_unit  # "C" or "F"
        self.current_weather_data: Optional[WeatherData] = None
        self.current_news_data: Optional[RegionalNewsResult] = None
        self._is_loading = False
        self._result_queue: queue.Queue[tuple[WeatherResult, Optional[RegionalNewsResult]]] = queue.Queue()

        # Build UI
        self._create_widgets()

        # Start periodic queue processor on main GUI thread
        self._schedule_queue_check()

        # Initial Load from preferences
        initial_city = self.preferences.last_city or "London"
        self.city_entry.insert(0, initial_city)
        self.after(100, lambda: self.start_weather_query(initial_city))

    def _create_widgets(self) -> None:
        """Construct the dark-mode layout hierarchy."""
        # Main Container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. Top Navigation & Search Bar
        self.header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#1a1e24")
        self.header_frame.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        self.header_frame.grid_columnconfigure(1, weight=1)

        self.app_title_label = ctk.CTkLabel(
            self.header_frame,
            text="🌦️ NewsWorld Weather",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#60a5fa",
        )
        self.app_title_label.grid(row=0, column=0, padx=16, pady=12)

        self.city_entry = ctk.CTkEntry(
            self.header_frame,
            placeholder_text="Enter city (e.g., Tokyo, London, Paris)...",
            font=ctk.CTkFont(size=14),
            height=38,
        )
        self.city_entry.grid(row=0, column=1, padx=8, pady=12, sticky="ew")
        self.city_entry.bind("<Return>", lambda e: self.on_search_clicked())

        self.search_button = ctk.CTkButton(
            self.header_frame,
            text="Search",
            command=self.on_search_clicked,
            width=90,
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.search_button.grid(row=0, column=2, padx=6, pady=12)

        self.locate_button = ctk.CTkButton(
            self.header_frame,
            text="📍 Locate Me",
            command=self.on_locate_clicked,
            width=100,
            height=38,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.locate_button.grid(row=0, column=3, padx=6, pady=12)

        # Unit Toggle
        self.unit_toggle = ctk.CTkSegmentedButton(
            self.header_frame,
            values=["°C", "°F"],
            command=self.on_unit_toggled,
            width=80,
            height=34,
        )
        self.unit_toggle.set("°C" if self.current_unit == "C" else "°F")
        self.unit_toggle.grid(row=0, column=4, padx=16, pady=12)

        # 2. Status / Error Message Banner
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready",
            font=ctk.CTkFont(size=13),
            text_color="#9ca3af",
            anchor="w",
        )
        self.status_label.grid(row=1, column=0, padx=20, pady=(0, 6), sticky="w")

        # 3. Scrollable Main Content Frame
        self.content_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content_scroll.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.content_scroll.grid_columnconfigure(0, weight=1)

        # --- Current Weather Hero Card ---
        self.hero_frame = ctk.CTkFrame(self.content_scroll, corner_radius=12, fg_color="#1e242c")
        self.hero_frame.grid(row=0, column=0, padx=4, pady=6, sticky="ew")
        self.hero_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.location_title = ctk.CTkLabel(
            self.hero_frame,
            text="--",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#f3f4f6",
        )
        self.location_title.grid(row=0, column=0, columnspan=3, padx=20, pady=(16, 2), sticky="w")

        self.timestamp_label = ctk.CTkLabel(
            self.hero_frame,
            text="Last updated: --",
            font=ctk.CTkFont(size=12),
            text_color="#9ca3af",
        )
        self.timestamp_label.grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 12), sticky="w")

        # Big Temp & Condition Icon
        self.weather_icon_label = ctk.CTkLabel(
            self.hero_frame,
            text="⛅",
            font=ctk.CTkFont(size=56),
        )
        self.weather_icon_label.grid(row=2, column=0, padx=20, pady=8, sticky="w")

        self.temperature_label = ctk.CTkLabel(
            self.hero_frame,
            text="--°",
            font=ctk.CTkFont(size=56, weight="bold"),
            text_color="#60a5fa",
        )
        self.temperature_label.grid(row=2, column=1, padx=8, pady=8, sticky="w")

        self.condition_label = ctk.CTkLabel(
            self.hero_frame,
            text="Loading...",
            font=ctk.CTkFont(size=20),
            text_color="#d1d5db",
        )
        self.condition_label.grid(row=2, column=2, padx=20, pady=8, sticky="w")

        # Metric Cards Container
        self.metrics_container = ctk.CTkFrame(self.hero_frame, fg_color="transparent")
        self.metrics_container.grid(row=3, column=0, columnspan=3, padx=16, pady=(12, 16), sticky="ew")
        self.metrics_container.grid_columnconfigure((0, 1, 2), weight=1)

        self.humidity_card = self._create_metric_card(self.metrics_container, 0, "💧 Humidity", "--%")
        self.wind_card = self._create_metric_card(self.metrics_container, 1, "💨 Wind Speed", "--")
        self.feels_card = self._create_metric_card(self.metrics_container, 2, "🌡️ Feels Like", "--°")

        # --- 6-Hour Hourly Forecast Section ---
        self.hourly_section = ctk.CTkFrame(self.content_scroll, corner_radius=12, fg_color="#1a1e24")
        self.hourly_section.grid(row=1, column=0, padx=4, pady=8, sticky="ew")
        self.hourly_section.grid_columnconfigure(0, weight=1)

        self.hourly_title = ctk.CTkLabel(
            self.hourly_section,
            text="⏱️ 6-Hour Hourly Trend",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#93c5fd",
        )
        self.hourly_title.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="w")

        self.hourly_cards_frame = ctk.CTkFrame(self.hourly_section, fg_color="transparent")
        self.hourly_cards_frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.hourly_cards_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.hourly_card_widgets: list[dict[str, ctk.CTkLabel]] = []
        for i in range(6):
            card = ctk.CTkFrame(self.hourly_cards_frame, corner_radius=8, fg_color="#262c36")
            card.grid(row=0, column=i, padx=4, pady=4, sticky="ew")
            lbl_time = ctk.CTkLabel(card, text="--", font=ctk.CTkFont(size=12, weight="bold"), text_color="#cbd5e1")
            lbl_time.pack(pady=(6, 2))
            lbl_icon = ctk.CTkLabel(card, text="☀️", font=ctk.CTkFont(size=24))
            lbl_icon.pack(pady=2)
            lbl_temp = ctk.CTkLabel(card, text="--°", font=ctk.CTkFont(size=13, weight="bold"), text_color="#60a5fa")
            lbl_temp.pack(pady=(2, 6))
            self.hourly_card_widgets.append({"time": lbl_time, "icon": lbl_icon, "temp": lbl_temp})

        # --- Bottom Grid: 5-Day Forecast & Regional News ---
        self.bottom_grid = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        self.bottom_grid.grid(row=2, column=0, padx=4, pady=8, sticky="ew")
        self.bottom_grid.grid_columnconfigure(0, weight=5)
        self.bottom_grid.grid_columnconfigure(1, weight=5)

        # 5-Day Outlook Card
        self.daily_frame = ctk.CTkFrame(self.bottom_grid, corner_radius=12, fg_color="#1a1e24")
        self.daily_frame.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="nsew")
        self.daily_frame.grid_columnconfigure(0, weight=1)

        self.daily_title = ctk.CTkLabel(
            self.daily_frame,
            text="📅 5-Day Daily Forecast",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#93c5fd",
        )
        self.daily_title.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="w")

        self.daily_rows_container = ctk.CTkFrame(self.daily_frame, fg_color="transparent")
        self.daily_rows_container.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.daily_rows_container.grid_columnconfigure(0, weight=1)
        self.daily_row_widgets: list[dict[str, ctk.CTkLabel]] = []
        for i in range(5):
            row_frame = ctk.CTkFrame(self.daily_rows_container, corner_radius=6, fg_color="#262c36")
            row_frame.grid(row=i, column=0, padx=2, pady=3, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            lbl_day = ctk.CTkLabel(row_frame, text="--", font=ctk.CTkFont(size=13, weight="bold"), width=90, anchor="w")
            lbl_day.grid(row=0, column=0, padx=10, pady=6)

            lbl_cond = ctk.CTkLabel(row_frame, text="☀️ --", font=ctk.CTkFont(size=12), anchor="w")
            lbl_cond.grid(row=0, column=1, padx=6, pady=6, sticky="w")

            lbl_range = ctk.CTkLabel(row_frame, text="--° / --°", font=ctk.CTkFont(size=13, weight="bold"), text_color="#60a5fa", width=80, anchor="e")
            lbl_range.grid(row=0, column=2, padx=10, pady=6)

            self.daily_row_widgets.append({"day": lbl_day, "cond": lbl_cond, "range": lbl_range})

        # Regional Breaking News Bridge Card
        self.news_frame = ctk.CTkFrame(self.bottom_grid, corner_radius=12, fg_color="#1a1e24")
        self.news_frame.grid(row=0, column=1, padx=(6, 0), pady=0, sticky="nsew")
        self.news_frame.grid_columnconfigure(0, weight=1)

        self.news_title = ctk.CTkLabel(
            self.news_frame,
            text="📰 Regional Breaking News",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#93c5fd",
        )
        self.news_title.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="w")

        self.news_items_container = ctk.CTkFrame(self.news_frame, fg_color="transparent")
        self.news_items_container.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.news_items_container.grid_columnconfigure(0, weight=1)
        self.news_item_widgets: list[dict[str, ctk.CTkLabel]] = []
        for i in range(3):
            item_box = ctk.CTkFrame(self.news_items_container, corner_radius=6, fg_color="#262c36")
            item_box.grid(row=i, column=0, padx=2, pady=3, sticky="ew")
            lbl_title = ctk.CTkLabel(
                item_box,
                text="--",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                justify="left",
                wraplength=400,
            )
            lbl_title.pack(padx=10, pady=(6, 2), anchor="w")
            lbl_meta = ctk.CTkLabel(item_box, text="--", font=ctk.CTkFont(size=10), text_color="#9ca3af", anchor="w")
            lbl_meta.pack(padx=10, pady=(0, 6), anchor="w")
            self.news_item_widgets.append({"title": lbl_title, "meta": lbl_meta})

    def _create_metric_card(self, parent: ctk.CTkFrame, col: int, label_text: str, default_val: str) -> dict[str, ctk.CTkLabel]:
        """Helper to create elevated metric card widget."""
        frame = ctk.CTkFrame(parent, corner_radius=8, fg_color="#262c36")
        frame.grid(row=0, column=col, padx=4, pady=4, sticky="ew")
        title = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=12), text_color="#9ca3af")
        title.pack(pady=(6, 0))
        val = ctk.CTkLabel(frame, text=default_val, font=ctk.CTkFont(size=18, weight="bold"), text_color="#f3f4f6")
        val.pack(pady=(0, 6))
        return {"title": title, "value": val}

    # ---------------- INTERACTION HANDLERS ----------------

    def on_search_clicked(self) -> None:
        """Handle user search button or enter key."""
        raw_city = self.city_entry.get().strip()
        if not raw_city:
            self.set_status("Please enter a city or location name.", is_error=True)
            return
        self.start_weather_query(raw_city)

    def on_locate_clicked(self) -> None:
        """Handle IP-based location auto-detection."""
        self.set_status("Detecting location via IP...", is_error=False)
        threading.Thread(target=self._run_locate_worker, daemon=True).start()

    def _run_locate_worker(self) -> None:
        success, city, error = self.weather_client.detect_ip_location()
        if success and city:
            self.after(0, lambda: self._apply_detected_location(city))
        else:
            self.after(0, lambda: self.set_status(f"Location detection failed: {error}", is_error=True))

    def _apply_detected_location(self, city: str) -> None:
        self.city_entry.delete(0, "end")
        self.city_entry.insert(0, city)
        self.start_weather_query(city)

    def on_unit_toggled(self, choice: str) -> None:
        """Switch between Celsius and Fahrenheit dynamically."""
        new_unit = "C" if choice == "°C" else "F"
        if new_unit == self.current_unit:
            return
        self.current_unit = new_unit
        self.preferences.temperature_unit = new_unit
        save_preferences(self.preferences)
        logger.info("Switched temperature unit to °%s", self.current_unit)
        if self.current_weather_data:
            self.render_weather(self.current_weather_data)

    def set_status(self, message: str, is_error: bool = False) -> None:
        """Update user status notification bar."""
        color = "#ef4444" if is_error else "#9ca3af"
        self.status_label.configure(text=message, text_color=color)

    # ---------------- NON-BLOCKING WORKER PIPELINE ----------------

    def start_weather_query(self, city_name: str) -> None:
        """Initiate asynchronous background query."""
        if self._is_loading:
            return
        self._is_loading = True
        self.search_button.configure(state="disabled")
        self.set_status(f"Fetching weather forecast for '{city_name}'...")

        threading.Thread(
            target=self._query_worker,
            args=(city_name,),
            name="WeatherWorker",
            daemon=True,
        ).start()

    def _query_worker(self, city_name: str) -> None:
        """Background thread executing weather and news network I/O."""
        weather_res = self.weather_client.fetch_weather(city_name)
        news_res: Optional[RegionalNewsResult] = None

        if weather_res.success and weather_res.data:
            country = weather_res.data.current.country
            news_res = self.news_bridge.fetch_regional_news(city_name, country=country)

        # Enqueue results to thread-safe queue and signal GUI main thread
        self._result_queue.put((weather_res, news_res))
        try:
            self.after(0, self._process_result_queue)
        except Exception:
            pass

    def _schedule_queue_check(self) -> None:
        """Poll thread-safe result queue from the main GUI thread."""
        self._process_result_queue()
        try:
            self.after(50, self._schedule_queue_check)
        except Exception:
            pass

    def _process_result_queue(self) -> None:
        """Drain queued background worker payloads on the main thread."""
        while not self._result_queue.empty():
            try:
                weather_res, news_res = self._result_queue.get_nowait()
                self._handle_query_results(weather_res, news_res)
            except queue.Empty:
                break

    def _handle_query_results(
        self,
        weather_res: WeatherResult,
        news_res: Optional[RegionalNewsResult],
    ) -> None:
        """Update GUI on the main thread after background worker finishes."""
        self._is_loading = False
        self.search_button.configure(state="normal")

        if not weather_res.success or not weather_res.data:
            err_msg = weather_res.error_message or "Failed to retrieve weather data."
            self.set_status(err_msg, is_error=True)
            return

        self.current_weather_data = weather_res.data
        self.current_news_data = news_res

        # Save successful city to user preferences
        self.preferences.last_city = weather_res.data.current.city
        save_preferences(self.preferences)

        # Render complete layout
        self.render_weather(weather_res.data)
        if news_res:
            self.render_news(news_res)

        self.set_status(f"Updated forecast for {weather_res.data.current.city}, {weather_res.data.current.country}.")

    # ---------------- DATA RENDERING ----------------

    def render_weather(self, data: WeatherData) -> None:
        """Populate GUI cards with WeatherData according to current unit."""
        self.current_weather_data = data
        curr = data.current
        is_c = self.current_unit == "C"

        # Hero Card
        loc_str = f"{curr.city}, {curr.country}" if curr.country else curr.city
        self.location_title.configure(text=loc_str)
        self.timestamp_label.configure(text=f"Atmospheric Report: {curr.timestamp}")
        self.weather_icon_label.configure(text=curr.icon)

        temp_val = f"{curr.temperature_c:.1f}°C" if is_c else f"{curr.temperature_f:.1f}°F"
        self.temperature_label.configure(text=temp_val)
        self.condition_label.configure(text=curr.condition)

        # Metrics
        self.humidity_card["value"].configure(text=f"{curr.humidity}%")
        wind_val = f"{curr.wind_speed_kmh:.1f} km/h" if is_c else f"{curr.wind_speed_mph:.1f} mph"
        self.wind_card["value"].configure(text=wind_val)
        feels_val = f"{curr.feels_like_c:.1f}°C" if is_c else f"{curr.feels_like_f:.1f}°F"
        self.feels_card["value"].configure(text=feels_val)

        # 6-Hour Hourly Trend
        for i, card_widgets in enumerate(self.hourly_card_widgets):
            if i < len(data.hourly):
                h = data.hourly[i]
                h_temp = f"{h.temperature_c:.0f}°" if is_c else f"{h.temperature_f:.0f}°"
                card_widgets["time"].configure(text=h.time_label)
                card_widgets["icon"].configure(text=h.icon)
                card_widgets["temp"].configure(text=h_temp)
            else:
                card_widgets["time"].configure(text="--")
                card_widgets["icon"].configure(text="--")
                card_widgets["temp"].configure(text="--°")

        # 5-Day Daily Outlook
        for i, row_widgets in enumerate(self.daily_row_widgets):
            if i < len(data.daily):
                d = data.daily[i]
                max_t = f"{d.temp_max_c:.0f}°" if is_c else f"{d.temp_max_f:.0f}°"
                min_t = f"{d.temp_min_c:.0f}°" if is_c else f"{d.temp_min_f:.0f}°"
                row_widgets["day"].configure(text=d.day_name)
                row_widgets["cond"].configure(text=f"{d.icon} {d.condition}")
                row_widgets["range"].configure(text=f"{max_t} / {min_t}")
            else:
                row_widgets["day"].configure(text="--")
                row_widgets["cond"].configure(text="--")
                row_widgets["range"].configure(text="--° / --°")

    def render_news(self, news: RegionalNewsResult) -> None:
        """Populate regional news cards or display empty state."""
        for i, item_widgets in enumerate(self.news_item_widgets):
            if news.success and i < len(news.headlines):
                h = news.headlines[i]
                item_widgets["title"].configure(text=h.title)
                meta_str = f"Source: {h.source}" + (f" • {h.published_at[:16]}" if h.published_at else "")
                item_widgets["meta"].configure(text=meta_str)
            else:
                item_widgets["title"].configure(
                    text="No regional breaking headlines available." if i == 0 else ""
                )
                item_widgets["meta"].configure(text="")
