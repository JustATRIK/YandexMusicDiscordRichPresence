import asyncio
import logging
import os
import sys
import threading
import time
import uuid
from typing import Optional
from urllib.parse import quote, quote_plus

import dotenv
import pystray
import requests
import json
from datetime import datetime, timedelta

from PIL import Image
from pypresence import Presence
from pystray import MenuItem
from winrt._winrt_windows_media_control import PlaybackInfoChangedEventArgs, MediaPropertiesChangedEventArgs, \
    SessionsChangedEventArgs
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSession as Session
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionMediaProperties as MediaProperties

import utils
from data import KNOWN_GENRES, Config, AuthInfo, ArtistInfo, Statistics, SongInfo, PlayInfo, RPCConfig, FontProvider, \
    AlbumInfo

from websocket import WebSocketApp

dotenv.load_dotenv(utils.DATA_DIR / ".env")

logging.basicConfig(level=logging.DEBUG if os.getenv("DEBUG").lower() == "true" else logging.INFO,
                    format="[%(asctime)s] [%(name)s]: %(message)s",
                    datefmt="%m-%d-%H:%M:%S",
                    handlers=[logging.StreamHandler(), logging.FileHandler(utils.DATA_DIR / "yamusic.log")],
                    encoding="utf-8")
logging.info("Initialized")

COOKIES = os.getenv("COOKIES")
USER_ID = os.getenv("USER_ID")

WEBSOCKET_URL = "wss://ynison.music.yandex.ru/redirector.YnisonRedirectService/GetRedirectToYnison"
DEVICE_ID = uuid.uuid4()
PAUSE_PLAYBACK_STATUS = 5

WARNED_GENRES = set()


class MusicApi:
    """
    Minimal API for YandexMusic required for RPC
    """

    def __init__(self, cookies: str, user_id: str):
        self.logger = logging.getLogger("MusicAPI")
        self._device_id: uuid = uuid.uuid4()
        self._user_id: str = user_id
        self._cookies: str = cookies
        self._auth_token: str = self.get_auth_token()
        self._auth_data: Optional[AuthInfo] = self.update_auth_data()
        self.logger.info("Loaded music api")

    def get_auth_token(self, session_id: str = None, redirect_ticket: str = None) -> str:
        """
        Generates and returns auth token, used by Yandex music service.
        session_id and redirect_ticket must be provided to get full access to the API
        :param session_id: Optional, ID of session
        :param redirect_ticket: Optional, Redirect ticket
        :return: Auth token
        """
        data: dict = {
            "Ynison-Device-Id": f"{self._device_id}",
            "Ynison-Device-Info": '{"app_name":"Chrome","app_version":"140.0.0.0","type":1}',
            "X-Yandex-Music-Multi-Auth-User-Id": f"{self._user_id}"
        }
        if session_id is not None:
            data["Ynison-Session-Id"] = session_id
        if redirect_ticket is not None:
            data["Ynison-Redirect-Ticket"] = redirect_ticket
        return quote(json.dumps(data))

    def update_auth_data(self) -> AuthInfo:
        """
        Updates, sets and returns new auth info
        :return: new AuthInfo
        """
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        new_auth: AuthInfo = AuthInfo()

        def on_message(ws: WebSocketApp, msg: str, new_auth: AuthInfo):
            self.logger.debug(f"Auth data request response")
            ws.close()
            new_auth.update(json.loads(msg))

        ws: WebSocketApp = WebSocketApp(
            WEBSOCKET_URL,
            header={
                f"Sec-WebSocket-Protocol": f"Bearer, V2, {self._auth_token}"
            },
            on_message=lambda ws, msg: on_message(ws, msg, new_auth),
            on_error=lambda ws, msg: ws.close(),
            cookie=COOKIES
        )

        ws.run_forever()
        self._auth_data = new_auth
        self._auth_token = self.get_auth_token(new_auth.session_id, new_auth.redirect_ticket)
        return new_auth

    def fetch_song_info(self, song_id: str) -> SongInfo:
        """
        Fetches and returns full song info, including artists and album data
        :param song_id:
        :return: SongInfo
        """
        response: requests.Response = requests.post("https://api.music.yandex.ru/tracks",
                                                    cookies={i.split("=")[0]: i.split("=")[1] for i in
                                                             self._cookies.split("; ")}, data={
                "trackIds": song_id,
                "removeDuplicates": True,
                "withProgress": False,
                "withMixData": False
            })
        self.logger.debug(f"Song request response {response.status_code}, {response.text}")
        song_data: dict = response.json()["result"][0]

        if len(song_data["albums"]) > 0:
            album_dict: dict = song_data["albums"][0]
            album_data: AlbumInfo = AlbumInfo(album_dict["id"], album_dict["title"], album_dict["year"],
                                              f"https://{album_dict["coverUri"][:-2]}1000x1000",
                                              album_dict["likesCount"], album_dict["genre"])
            song_url: str = f"https://music.yandex.ru/album/{album_data.id}/track/{song_id}"
        else:
            # If there's no album data, song was uploaded by user. Using simple fallback album data
            album_data: AlbumInfo = AlbumInfo(-1, "Unknown", -1,
                                              "https://avatars.yandex.net/get-music-content/16450533/0286368d.a.40316159-1/1000x1000",
                                              -1, "Unknown")
            song_url: str = "https://www.youtube.com/results?search_query=" + quote_plus(
                song_data["title"] + " " + song_data["artists"][0]["name"])

        artists: list[ArtistInfo] = []
        for artist in song_data["artists"]:
            cover_url: str = "idtdq6n_ea_1760019159573_1_"
            # Same here, if song was uploaded by user, the information will be minimal (like only artists name)
            # So we're using fallback information

            if "cover" in artist:
                cover_url = artist["cover"]["uri"][:-2] + "200x200"
                if not cover_url.startswith("https"):
                    cover_url = "https://" + cover_url

            if "id" not in artist:
                artist["id"] = -1
                artist_url: str = "https://www.youtube.com/results?search_query=" + quote_plus(artist["name"])
            else:
                artist_url: str = "https://music.yandex.ru/artist/" + str(artist["id"])

            artists.append(ArtistInfo(artist["id"], artist["name"], cover_url, artist_url))

        return SongInfo(song_id, song_data["title"], artists, song_url,
                        song_data["contentWarning"] if "contentWarning" in song_data else None, album_data)

    def get_new_play_info(self) -> PlayInfo:
        """
        Fetches and returns current play info (basically song queue and current index in this queue)
        :return: PlayInfo
        """
        self.update_auth_data()

        def on_message(ws: WebSocketApp, message: str, play_info: PlayInfo):
            ws.close()
            self.logger.debug(f"Play info updated")
            play_info.update(json.loads(message))

        def on_open(ws: WebSocketApp):
            data = {
                "update_full_state": {
                    "player_state": {
                        "player_queue": {
                            "current_playable_index": -1,
                            "entity_id": "",
                            "entity_type": "VARIOUS",
                            "playable_list": [],
                            "options": {
                                "repeat_mode": "NONE"
                            },
                            "shuffle_optional": None,
                            "entity_context": "BASED_ON_ENTITY_BY_DEFAULT",
                            "version": {
                                "device_id": str(self._device_id),
                                "version": 7680276980327254000,
                                "timestamp_ms": 0
                            },
                            "from_optional": "",
                            "initial_entity_optional": None,
                            "adding_options_optional": None,
                            "queue": None
                        },
                        "status": {
                            "duration_ms": 0,
                            "paused": True,
                            "playback_speed": 1,
                            "progress_ms": 0,
                            "version": {
                                "device_id": str(self._device_id),
                                "version": 4001644781241097000,
                                "timestamp_ms": 0
                            }
                        },
                        "player_queue_inject_optional": None
                    },
                    "device": {
                        "volume": 1,
                        "capabilities": {
                            "can_be_player": True,
                            "can_be_remote_controller": False,
                            "volume_granularity": 16
                        },
                        "info": {
                            "app_name": "Chrome",
                            "app_version": "140.0.0.0",
                            "title": "Browser Chrome",
                            "device_id": str(self._device_id),
                            "type": "WEB"
                        },
                        "volume_info": {
                            "volume": 0,
                            "version": None
                        },
                        "is_shadow": True
                    },
                    "is_currently_active": False,
                    "sync_state_from_eov_optional": None
                },
                "rid": str(uuid.uuid4()),
                "player_action_timestamp_ms": 0,
                "activity_interception_type": "DO_NOT_INTERCEPT_BY_DEFAULT"
            }
            str_data = json.dumps(data)
            ws.send_text(str_data)

        play_info = PlayInfo()

        ws: WebSocketApp = WebSocketApp(
            f"wss://{self._auth_data.host}/ynison_state.YnisonStateService/PutYnisonState",
            header={
                f"Sec-WebSocket-Protocol": f"Bearer, V2, {self._auth_token}",
            },
            on_message=lambda ws, msg: on_message(ws, msg, play_info),
            on_error=lambda ws, msg: ws.close(),
            on_open=on_open,
            cookie=COOKIES
        )
        ws.run_forever()

        return play_info


class SyncMediaManager:
    """
    Wrapper around winrt's MediaManager to use it synchronously
    """

    def __init__(self):
        self.sessions: Optional[MediaManager] = None
        self.update_sessions()

    async def request_async(self) -> None:
        self.sessions = await MediaManager.request_async()

    def update_sessions(self) -> None:
        """
        Calls request_async synchronously
        :return:
        """
        logging.debug("Updating media sessions")
        asyncio.run(self.request_async())
        logging.debug("Updated media sessions")

    def get_current_sessions(self) -> list[Session]:
        """
        :return: List of all current sessions
        """
        return list(self.sessions.get_sessions())

    @staticmethod
    def get_mediainfo(session: Session) -> Optional[MediaProperties]:
        """
        Synchronously requests session info
        :param session: Media session
        :return: Optional MediaProperties
        """
        return asyncio.run(SyncMediaManager.request_mediainfo(session))

    @staticmethod
    def update_timeline(session: Session) -> None:
        """
        Forces window to update session's timeline property by pausing and unpausing session
        :param session: Media session
        :return:
        """
        asyncio.run(SyncMediaManager._update_timeline(session))

    @staticmethod
    async def _update_timeline(session: Session) -> None:
        await session.try_toggle_play_pause_async()
        await asyncio.sleep(0.05)
        await session.try_toggle_play_pause_async()

    @staticmethod
    async def request_mediainfo(session: Session) -> Optional[MediaProperties]:
        return await session.try_get_media_properties_async()


class RPCManager:
    """
    Rich Presence manager
    """

    def __init__(self, music_api: MusicApi, media_manager: SyncMediaManager):
        self.logger = logging.getLogger("RPCManager")

        self.statistics: Statistics = Statistics.load(utils.DATA_DIR / "statistic.json", lambda: Statistics())
        utils.PLACEHOLDER_MANAGER.register_provider("statistics", self.statistics)
        self.logger.info(f"Loaded statistic")

        self.config: Config = Config.load(utils.DATA_DIR / "config.json", lambda: Config())
        self.config.save()
        self.logger.info(f"Loaded config {self.config}")

        self.font_provider: FontProvider = FontProvider.load(utils.DATA_DIR / "fonts.json", lambda: FontProvider())
        if not os.path.exists(self.font_provider.file_path):
            self.font_provider.save()
        utils.PLACEHOLDER_MANAGER.register_provider("font", self.font_provider)

        self.music_api: MusicApi = music_api
        self.media_manager: SyncMediaManager = media_manager
        self.rpc: Optional[Presence] = None
        self.yandex_session: Optional[Session] = self.try_find_yandex_session()
        self.__subscribe_to_session_events()
        media_manager.sessions.add_sessions_changed(self.__on_sessions_changed)

        self.data_changed: bool = False

        self.working_time: int = 0
        self.session_changed_at: int = 0

        self.paused: bool = False
        self.audio_start_time: datetime = datetime.min
        self.audio_end_time: datetime = datetime.min
        self.api_song_title: str = ""
        self.app_song_title: str = ""

        self.song_info: Optional[SongInfo] = None

        # After everything initialized start RPC
        if self.yandex_session:
            self.audio_start_time = datetime.now()
            self.audio_end_time = self.audio_start_time + self.yandex_session.get_timeline_properties().end_time

            app_song_data: Optional[MediaProperties] = SyncMediaManager.get_mediainfo(self.yandex_session)
            if app_song_data:
                self.app_song_title = app_song_data.title

            SyncMediaManager.update_timeline(self.yandex_session)
            self.paused = self.yandex_session.get_playback_info().playback_status == 5
            self.connect_to_discord()

    def __on_playback_change(self, session: Session, args: PlaybackInfoChangedEventArgs):
        self.paused = session.get_playback_info().playback_status == PAUSE_PLAYBACK_STATUS

    def __on_mediainfo_change(self, session: Session, args: MediaPropertiesChangedEventArgs):
        self.audio_start_time = datetime.now()
        new_data: Optional[MediaProperties] = SyncMediaManager.get_mediainfo(session)
        if new_data:
            self.app_song_title = new_data.title

    def __on_timeline_changed(self, session: Session, args: MediaPropertiesChangedEventArgs):
        self.audio_start_time -= session.get_timeline_properties().position - timedelta(
            seconds=int(datetime.now().timestamp() - self.audio_start_time.timestamp()))
        self.audio_end_time = self.audio_start_time + session.get_timeline_properties().end_time
        self.data_changed = True

    def __on_sessions_changed(self, manager: MediaManager, args: SessionsChangedEventArgs):
        self.yandex_session = self.try_find_yandex_session()
        self.subscribe_to_session_events()
        self.session_changed_at = self.working_time
        self.logger.info(f"Sessions changed. Yandex session {self.yandex_session}")

    def try_find_yandex_session(self) -> Optional[Session]:
        """
        Searches for YandexMusics session
        :return: Optional of Media Session
        """
        for session in self.media_manager.sessions.get_sessions():
            if session.source_app_user_model_id == self.config.app_id:
                return session
        return None

    def __subscribe_to_session_events(self) -> None:
        """
        Hooks events to YandexMusic session
        :return:
        """
        if self.yandex_session:
            self.yandex_session.add_playback_info_changed(self.__on_playback_change)
            self.yandex_session.add_media_properties_changed(self.__on_mediainfo_change)
            self.yandex_session.add_timeline_properties_changed(self.__on_timeline_changed)

    def connect_to_discord(self) -> bool:
        """
        Tries to connect to Discord local server
        :return: bool, was connection successful
        """
        if self.rpc:
            self.rpc.close()

        try:
            self.rpc = Presence(self.config.presence_id)
            self.rpc.connect()
            return True
        except Exception:
            self.logger.debug("Failed to start rpc", exc_info=True)
            return False

    def update_rpc(self, use_second_large: bool = False) -> None:
        """
        Calculates data and updates Rich Presence with it
        :param use_second_large: Wheter should use second_large_text defined in cfg instead of first
        :return:
        """
        if self.rpc:
            if self.song_info.album.genre not in KNOWN_GENRES and self.song_info.album.genre not in WARNED_GENRES:
                # Warn in console about new genre which doesn't have translation defined in program
                self.logger.warning(f"Found unknown genre {self.song_info.album.genre}")
                WARNED_GENRES.add(self.song_info.album.genre)

            self.logger.debug(f"Updating RPC for song {self.song_info.title}")

            rpc_config: RPCConfig = self.config.rpc_config
            try:
                self.rpc.update(
                    start=int(self.audio_start_time.timestamp() * 1000),
                    end=int(self.audio_end_time.timestamp() * 1000),
                    details=utils.PLACEHOLDER_MANAGER.gather_all(rpc_config.details),
                    state=utils.PLACEHOLDER_MANAGER.gather_all(rpc_config.state),
                    large_text=utils.PLACEHOLDER_MANAGER.gather_all(
                        rpc_config.large_text_second if use_second_large else rpc_config.large_text_first),
                    details_url=utils.PLACEHOLDER_MANAGER.gather_all(rpc_config.details_url),
                    status_url=utils.PLACEHOLDER_MANAGER.gather_all(rpc_config.status_url),
                    large_image=utils.PLACEHOLDER_MANAGER.gather_all(rpc_config.large_image),
                    small_image=utils.PLACEHOLDER_MANAGER.gather_all(rpc_config.small_image),
                    small_text=utils.PLACEHOLDER_MANAGER.gather_all(rpc_config.small_text),
                    instance=False
                )
            except Exception as e:
                self.rpc = None
                self.logger.error(f"Failed to update rpc: {e}", exc_info=True)

    def loop_tick(self) -> None:
        """
        Executes one program tick
        :return:
        """
        if not utils.is_discord_opened():
            self.stop_rpc("Discord isn't opened")
            return

        # For some reason, session becomes None without event
        # So we update session_changed_at every tick when sessions isn't None
        if self.yandex_session:
            self.session_changed_at = self.working_time
            if self.working_time % 2 == 0:
                if self.paused:
                    # Stop RPC if music is paused
                    self.stop_rpc("Music is paused")
                    self.data_changed = True
                    return
                else:
                    # Increase listened time
                    self.statistics.listened_time += 1

            should_send_updates: bool = False

            # Check if we should request new info from API
            if self.api_song_title != self.app_song_title:
                should_send_updates = True
                play_info: PlayInfo = self.music_api.get_new_play_info()

                self.logger.info(f"Updating song info. Required {self.app_song_title}")
                if not play_info.song_list:
                    self.logger.warning("Failed to fetch song data")
                    return

                old_song_info: SongInfo = self.song_info

                try:
                    self.song_info = self.music_api.fetch_song_info(play_info.song_list[play_info.current_song_index])
                except Exception as e:
                    self.logger.error("Failed to fetch song info")
                    self.logger.error(e)

                if old_song_info and old_song_info.id != self.song_info.id:
                    # Update songs count statistic
                    self.statistics.increase_statistic(old_song_info)

                self.api_song_title = self.song_info.title
                self.logger.info(f"Got song from API: {self.api_song_title}")
                # Update placeholders providers
                utils.PLACEHOLDER_MANAGER.register_provider("album", self.song_info.album)
                utils.PLACEHOLDER_MANAGER.register_provider("song", self.song_info)
                utils.PLACEHOLDER_MANAGER.register_provider("main_artist", self.song_info.artists[0])

            # Force updates every 10 seconds
            should_send_updates |= self.working_time % 20 == 0 or self.data_changed

            if should_send_updates:
                self.data_changed = False
                if not self.rpc:
                    if not self.connect_to_discord():
                        return

                # Check
                self.update_rpc(self.working_time % (
                        self.config.large_text_switch_seconds * 4) >= self.config.large_text_switch_seconds * 2)
        elif self.working_time - self.session_changed_at > 6:
            # If there's no Yandex session, stop rpc after 3 seconds of session update
            # If do it instantly, right after song ends session sets to None
            # And we stop RPC even though next song is just not loaded yet
            self.stop_rpc("Session is None")

        # Save statistics every 10 seconds
        if self.working_time % 20 == 0:
            self.statistics.save()
        self.working_time += 1

    def stop_rpc(self, reason: str = "None") -> None:
        """
        Clears RPC and stops server
        :return:
        """
        if self.rpc:
            self.logger.debug("Stopping rpc. Current rpc " + str(self.rpc))
            try:
                self.rpc.clear()
                self.rpc.close()
                self.logger.info(f"Stopped rpc. Reason {reason}")
            except Exception as e:
                self.logger.warning("Failed to stop rpc")
                self.logger.warning(e)
                return
        self.rpc = None


if __name__ == "__main__":
    work_thread: threading.Thread

    def run_work_thread() -> None:
        global work_thread
        work_thread = threading.Thread(target=work_loop, daemon=True)
        work_thread.start()


    def exception_logger_hook(args):
        if not issubclass(args.exc_type, KeyboardInterrupt):
            logging.critical("Uncaught exception occurred",
                             exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        # Log all errors in all threads
        sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)
        if args.thread == work_thread:
            logging.warning("Exception was raised in work thread. Restarting this thread")
            run_work_thread()

    threading.excepthook = exception_logger_hook

    working_event: threading.Event = threading.Event()
    config_reload_event: threading.Event = threading.Event()


    def work_loop() -> None:
        rpc_manager: RPCManager = RPCManager(MusicApi(COOKIES, USER_ID), SyncMediaManager())
        while not working_event.is_set():
            rpc_manager.loop_tick()

            # Reload config and font provider
            if config_reload_event.is_set():
                rpc_manager.config.reload()
                rpc_manager.font_provider.reload()
                rpc_manager.data_changed = True
                config_reload_event.clear()

            time.sleep(0.5)
        rpc_manager.stop_rpc("Program exited")


    def quit_action(icon_instance: pystray.Icon, item: MenuItem):
        working_event.set()
        icon_instance.stop()


    def config_reload_action(icon_instance: pystray.Icon, item: MenuItem):
        config_reload_event.set()


    icon: pystray.Icon = pystray.Icon(
        name="YaMusicRPC",
        title="YaMusicRPC",
        icon=Image.open(utils.STATIC_DIR / "icon.ico"),
        menu=pystray.Menu(
            pystray.MenuItem("Перезагрузить конфиг", config_reload_action),
            pystray.MenuItem("Закрыть", quit_action),
        )
    )

    run_work_thread()
    logging.info("Started app")

    icon.run()
