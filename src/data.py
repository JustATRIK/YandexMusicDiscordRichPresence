import dataclasses
import logging
from typing import Optional

import utils
from utils import PlaceholderProvider, ReloadableJson, JsonSerializable

# Store known genres translations
KNOWN_GENRES = {
    "Unknown": "Неизвестно",
    "rock": "Рок",
    "pop": "Поп",
    "alternativemetal": "Альтернативный метал",
    "metal": "Метал",
    "alternative": "Альтернатива",
    "numetal": "Ню-метал",
    "industrial": "Индастриал",
    "metalcoregenre": "Металкор",
    "dnb": "Драм-н-бейс",
    "electronics": "Электронная музыка",
    "indie": "Инди",
    "posthardcore": "Постхардкор",
    "rap": "Рэп",
    "foreignrap": "Рэп",
    "punk": "Панк",
    "soundtrack": "Саундтрек",
    "edmgenre": "Электронная танцевальная музыка",
    "progmetal": "Прогрессивный метал",
}


@dataclasses.dataclass
class ArtistInfo(PlaceholderProvider):
    """
    Class which represents artist info
    """

    id: int
    name: str
    cover_url: str
    artist_url: str

    def get_data(self, query: str) -> str:
        for key, value in self.__dict__.items():
            if key == query:
                return str(value)
        return query


@dataclasses.dataclass
class AlbumInfo(PlaceholderProvider):
    """
    Class which represents album info
    """

    id: int
    title: str
    year: int
    cover_url: str
    likes_count: int
    genre: str

    def get_data(self, query: str) -> str:
        if query == "genre":
            if self.genre in KNOWN_GENRES:
                return KNOWN_GENRES[self.genre]
            return self.genre

        for key, value in self.__dict__.items():
            if key == query:
                if value == -1:
                    return "?"
                if value == "Unknown":
                    return "Неизвестно"
                return str(value)
        return query


@dataclasses.dataclass
class SongInfo(PlaceholderProvider):
    """
    Class which represents song info
    """

    id: str
    title: str
    artists: list[ArtistInfo]
    song_url: str
    content_warning: Optional[str]
    album: AlbumInfo

    def get_data(self, query: str) -> str:
        if query == "artists":
            return ", ".join([artist.name for artist in self.artists])

        for key, value in self.__dict__.items():
            if key == query:
                return str(value)
        return query


@dataclasses.dataclass
class PlayInfo:
    """
    Class which represents play info
    """

    current_song_index: int = None
    song_list: list[str] = None

    def update(self, data: dict):
        player_queue = data["player_state"]["player_queue"]
        self.current_song_index = player_queue["current_playable_index"]
        self.song_list = [x["playable_id"] for x in player_queue["playable_list"]]


@dataclasses.dataclass
class AuthInfo:
    """
    Class which represents auth info
    """

    redirect_ticket: str = None
    session_id: str = None
    host: str = None

    def update(self, data: dict):
        self.redirect_ticket = data["redirect_ticket"]
        self.session_id = data["session_id"]
        self.host = data["host"]

    def __str__(self):
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        return "AuthInfo"

    def __repr__(self):
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        # DO NOT EXPOSE AUTH DATA TO LOGS!!!
        return "AuthInfo"


@dataclasses.dataclass
class RPCConfig(JsonSerializable):
    """
    Class which represents RPC string config
    """

    details: str = "[font.bold_capital:[song.title]]"
    details_url: str = "[song.song_url]"

    state: str = "🎧[album.title] ([album.likes_count]♥) от [song.artists]"
    status_url: str = "[main_artist.artist_url]"

    large_image: str = "[album.cover_url]"
    large_text_first: str = "📻[album.genre] | [statistics.listened_tracks_count], [statistics.listened_time]"
    large_text_second: str = "😻TØP [statistics.listened_by_artist:twenty one pilots] | [statistics.most_listened_genre_name] [statistics.most_listened_genre_count]"

    small_image: str = "[main_artist.cover_url]"
    small_text: str = "[main_artist.name]"


@dataclasses.dataclass
class Config(ReloadableJson):
    """
    Class which represents global config
    """

    rpc_config: RPCConfig = dataclasses.field(default_factory=RPCConfig)
    large_text_switch_seconds: int = 10
    app_id: str = "ru.yandex.desktop.music"
    presence_id: str = "1425844675536748665"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class Statistics(ReloadableJson, PlaceholderProvider):
    """
    Class which represents statistic info
    """

    listened_songs_count: int = 0
    listened_songs_by_genres: dict[str, int] = dataclasses.field(default_factory=dict)
    listened_songs_by_artists: dict[str, int] = dataclasses.field(default_factory=dict)
    listened_time: int = 0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def increase_statistic(self, song_info: SongInfo):
        """
        Increase statistic for specific song album and artist
        :param song_info: Song for which statistic should be increases
        :return:
        """
        if song_info.album.genre in self.listened_songs_by_genres:
            self.listened_songs_by_genres[song_info.album.genre] += 1
        else:
            self.listened_songs_by_genres[song_info.album.genre] = 1

        if song_info.artists[0].name in self.listened_songs_by_artists:
            self.listened_songs_by_artists[song_info.artists[0].name] += 1
        else:
            self.listened_songs_by_artists[song_info.artists[0].name] = 1

        self.listened_songs_count += 1

    def get_data(self, query: str) -> str:
        match query.strip():
            case "listened_tracks_count": return str(self.listened_songs_count) + " " + utils.tracks_count_name_for_count(self.listened_songs_count)
            case "most_listened_genre_name": return self.most_listened_genre()[0]
            case "most_listened_genre_count":
                count: int = self.most_listened_genre()[1]
                return str(count) + " " + utils.tracks_count_name_for_count(count)
            case "most_listened_artist_name":
                return self.most_listened_genre()[0]
            case "most_listened_artist_count":
                count: int = self.most_listened_genre()[1]
                return str(count) + " " + utils.tracks_count_name_for_count(count)
            case "listened_time":
                return self.formatted_listened_time()

        if query.startswith("listened_by_genre:"):
            genre: str = query.replace("listened_by_genre:", "").strip()
            count: int = self.listened_by_genre(genre)
            return str(count) + " " + utils.tracks_count_name_for_count(count)
        elif query.startswith("listened_by_artist:"):
            artist: str = query.replace("listened_by_artist:", "").strip()
            count: int = self.listened_by_artist(artist)
            return str(count) + " " + utils.tracks_count_name_for_count(count)

        return query

    def most_listened_genre(self) -> Optional[tuple[str, int]]:
        if len(self.listened_songs_by_genres) < 1:
            return None

        most_listened_genre = max(self.listened_songs_by_genres.keys(),
                                  key=lambda genre: self.listened_songs_by_genres[genre])
        most_listened_genre_count = self.listened_songs_by_genres[most_listened_genre]
        if most_listened_genre in KNOWN_GENRES:
            most_listened_genre = KNOWN_GENRES[most_listened_genre]

        return most_listened_genre, most_listened_genre_count

    def most_listened_artist(self) -> Optional[tuple[str, int]]:
        if len(self.listened_songs_by_artists) < 1:
            return None

        most_listened_artist = max(self.listened_songs_by_artists.keys(),
                                  key=lambda genre: self.listened_songs_by_artists[genre])
        most_listened_artist_count = self.listened_songs_by_artists[most_listened_artist]

        return most_listened_artist, most_listened_artist_count

    def listened_by_artist(self, artist: str) -> int:
        return self.listened_songs_by_artists[artist] if artist in self.listened_songs_by_artists else 0

    def listened_by_genre(self, genre: str) -> int:
        return self.listened_songs_by_genres[genre] if genre in self.listened_songs_by_genres else 0

    def listened_seconds(self) -> int:
        return self.listened_time

    def formatted_listened_time(self) -> str:
        listen_time_hours: int = self.listened_time // 3600
        listen_time_minutes: int = self.listened_time // 60 % 60

        listen_time_message: str = f"{listen_time_minutes}м."
        if listen_time_hours > 0:
            listen_time_message = f"{listen_time_hours}ч. " + listen_time_message

        return listen_time_message

@dataclasses.dataclass
class FontData(JsonSerializable):
    """
    Class which represents font data
    """

    symbols_mapping: dict[str, str] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        original_symbols: str = ""
        replaced_symbols: str = ""
        for o, r in self.symbols_mapping.items():
            original_symbols += o
            replaced_symbols += r
        return {
            "original_symbols": original_symbols,
            "replaced_symbols": replaced_symbols,
        }

    def update_from_dict(self, data: dict) -> None:
        original_symbols: str = data["original_symbols"]
        replaced_symbols: str = data["replaced_symbols"]
        if len(replaced_symbols) != len(original_symbols):
            logging.warning("Original and replaced symbols has different length!")

        for ind in range(min(len(original_symbols), len(replaced_symbols))):
            self.symbols_mapping[original_symbols[ind]] = replaced_symbols[ind]

    def replace_all(self, text: str) -> str:
        """
        Replaces text's symbols with specific font
        :param text: Text in which text should be replaced
        :return: Replaced string
        """
        result: str = ""
        for symbol in text:
            if symbol in self.symbols_mapping:
                result += self.symbols_mapping[symbol]
            else:
                result += symbol
        return result

@dataclasses.dataclass
class FontProvider(ReloadableJson, PlaceholderProvider):
    """
    Class which controls fonts data
    """

    fonts: dict[str, FontData] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        res: dict = {}
        for provider_name, font_data in self.fonts.items():
            res[provider_name] = font_data.to_dict()
        return res

    def update_from_dict(self, data: dict) -> None:
        for provider_name, font_data in data.items():
            self.fonts[provider_name] = FontData.from_dict(font_data)

    def get_data(self, query: str) -> str:
        data: list[str] = query.split(":")
        font_provider: str = data[0]
        text: str = data[1]

        if font_provider not in self.fonts:
            logging.warning(f"Font data {font_provider} not found")
            return text

        return self.fonts[font_provider].replace_all(text)
