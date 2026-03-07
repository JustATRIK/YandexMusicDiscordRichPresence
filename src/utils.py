import json
import os
import sys
from collections.abc import Callable
from os import PathLike
from pathlib import Path
from typing import Self, Optional

import psutil


# Get working dir dependent on how the program is executing
if getattr(sys, "frozen", False):
    EXE_DIR: Path = Path(os.path.dirname(sys.executable))
else:
    EXE_DIR: Path = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "run"
DATA_DIR: Path = EXE_DIR / "data"
if not DATA_DIR.exists():
    DATA_DIR.mkdir()

STATIC_DIR: Path = EXE_DIR / "static"


class PlaceholderProvider:

    def get_data(self, query: str) -> str:
        """
        Returns replaced query
        :param query: String representing query
        :return: Replaced query
        """
        raise NotImplementedError("Must be implemented")


class PlaceholderManager:

    def __init__(self):
        self.__registered_providers: dict[str, PlaceholderProvider] = dict()

    def register_provider(self, data: str, provider: PlaceholderProvider) -> None:
        """
        Registers new provider
        :param data: Provider name
        :param provider: Provider instance
        :return:
        """
        self.__registered_providers[data] = provider

    def gather_all(self, target_str: str) -> str:
        """
        Replaces all placeholders in provided string. Firstly replaces placeholders which are deeper.
        For example, in '[provider1.name1[provider2.name2]]' '[provider2.name2]' will be replaced first
        :param target_str: String in which placeholders should be replaced
        :return: String in which all placeholders replaced
        """
        placeholders: list[str] = remove_duplicates(find_all_data_in_brackets(target_str))
        for index, placeholder in enumerate(placeholders):
            data: tuple[str, ...] = tuple(placeholder[1:-1].split("."))
            provider_name: str = data[0]
            provider_query: str = ".".join(data[1:])

            result = self.__registered_providers[provider_name].get_data(provider_query)

            for inner_placeholder_ind in range(index + 1, len(placeholders)):
                placeholders[inner_placeholder_ind] = placeholders[inner_placeholder_ind].replace(placeholder, result)
            target_str = target_str.replace(placeholder, result)
        return target_str


class JsonSerializable:
    """
    Describes json (dict) serialization and deserialization
    """

    def to_dict(self) -> dict:
        """
        Coverts class data to dict
        :return: Class data represented as dict
        """
        raise NotImplementedError("Must be implemented")

    def update_from_dict(self, data: dict) -> None:
        """
        Updates class data from dict
        :param data: Dict from which data will be used
        :return:
        """
        annotations: dict[str, type] = self.__annotations__
        for atr_name in self.__dict__.keys():
            if atr_name in data:
                if atr_name in annotations:
                    attr_type: type = annotations[atr_name]
                    if issubclass(attr_type, JsonSerializable):
                        self.__dict__[atr_name] = attr_type.from_dict(data[atr_name])
                        continue
                self.__dict__[atr_name] = data[atr_name]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Deserializes and creates new class instance
        :param data: Data from which data will be used
        :return: Deserialized object
        """
        instance: Self = cls()
        instance.update_from_dict(data)
        return instance


class SavableFile:
    """
    Class for I/O operations with object
    """

    def __init__(self, file_path: PathLike):
        self.file_path = file_path

    def save(self) -> None:
        """
        Saves data to file
        :return:
        """
        raise NotImplementedError("Must be implemented")

    def reload(self) -> None:
        """
        Reloads data from file
        :return:
        """
        raise NotImplementedError("Must be implemented")

    @classmethod
    def load(cls, file_path: PathLike, fallback: Optional[Callable[[], Self]] = None) -> Self:
        """
        Load and creates new class instance from file.
        Fallback factory will be used if file doesn't exist
        :param file_path:
        :param fallback: Fallback factory
        :return: Loaded object
        """
        raise NotImplementedError("Must be implemented")


class ReloadableJson(SavableFile, JsonSerializable):
    """
    Class which stores data as json (dict) and support I/O operations
    """

    def save(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=4, ensure_ascii=False)

    def reload(self) -> None:
        with open(self.file_path, "r", encoding="utf-8") as file:
            data: dict = json.load(file)
            self.update_from_dict(data)

    @classmethod
    def load(cls, file_path: PathLike, fallback_supplier: Optional[Callable[[], Self]] = None) -> Self:
        if not os.path.exists(file_path):
            if not fallback_supplier:
                return None
            instance: Self = fallback_supplier()
            instance.file_path = file_path
            return instance
        with open(file_path, "r", encoding="utf-8") as file:
            data: dict = json.load(file)
            instance: Self = cls.from_dict(data)
            instance.file_path = file_path
            return instance


PLACEHOLDER_MANAGER = PlaceholderManager()


def is_discord_opened() -> bool:
    """
    Checks whether Discord is opened
    :return: Is Discord opened
    """
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"].lower() == "discord.exe":
            return True
    return False


def tracks_count_name_for_count(count: int) -> str:
    """
    Returns "трек" word in correct spelling for provided tracks count
    :param count: Number of tracks
    :return: "трек" word in correct spelling
    """
    last_digit: int = count % 10
    last_two_digits: int = count % 100
    if last_digit == 0 or 10 <= last_two_digits <= 20 or last_digit > 4:
        return "треков"
    elif last_digit == 1:
        return "трек"
    else:
        return "трека"


def remove_duplicates(data: list[str]) -> list[str]:
    """
    Removes duplicates from list
    :param data: List which should be filtered
    :return: Data without duplicates
    """
    used_data: set[str] = set()
    result: list[str] = []
    for string in data:
        if string not in used_data:
            used_data.add(string)
            result.append(string)

    return result


def find_all_data_in_brackets(text: str) -> list[str]:
    """
    Finds and returns all data in brackets
    :param text: Text in which brackets should be searched
    :return: Sorted list of strings in brackets
    """
    result = list()
    stack = []

    for i, char in enumerate(text):
        if char == "[":
            stack.append(i)
        elif char == "]" and stack:
            start = stack.pop()
            result.append(text[start:i + 1])

    return result
