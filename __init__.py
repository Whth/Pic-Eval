import os
import pathlib
import re
from typing import List

from modules.file_manager import get_pwd
from modules.plugin_base import AbstractPlugin

__all__ = ["PicEval"]


class Default:
    asset = f"{get_pwd()}/asset"
    recycle = f"{get_pwd()}/recycled"
    cache = f"{get_pwd()}/cache"
    store = f"{get_pwd()}/store"

    @classmethod
    def create_folders(cls):
        default = [cls.asset, cls.recycle, cls.cache, cls.store]
        for attr in default:
            pathlib.Path(attr).mkdir(parents=True, exist_ok=True)


class PicEval(AbstractPlugin):
    CONFIG_PICTURE_ASSET_PATH = "PictureAssetPath"
    CONFIG_PICTURE_IGNORED_DIRS = "PictureIgnored"
    CONFIG_PICTURE_CACHE_DIR_PATH = "PictureCacheDirPath"
    CONFIG_STORE_DIR_PATH = "StoreDirPath"
    CONFIG_LEVEL_RESOLUTION = "LevelResolution"

    CONFIG_DETECTED_KEYWORD = "DetectedKeyword"

    CONFIG_RAND_KEYWORD = "RandKeyword"

    CONFIG_MAX_FILE_SIZE = "MaxFileSize"

    CONFIG_RECYCLE_FOLDER = "RecycleFolder"

    CONFIG_MAX_BATCH_SIZE = "MaxBatchSize"

    Default.create_folders()
    DefaultConfig = {
        CONFIG_PICTURE_ASSET_PATH: Default.asset,
        CONFIG_RECYCLE_FOLDER: Default.recycle,
        CONFIG_PICTURE_CACHE_DIR_PATH: Default.cache,
        CONFIG_STORE_DIR_PATH: Default.store,
        CONFIG_PICTURE_IGNORED_DIRS: [],
        CONFIG_DETECTED_KEYWORD: "eval",
        CONFIG_RAND_KEYWORD: "ej",
        CONFIG_LEVEL_RESOLUTION: 10,
        CONFIG_MAX_FILE_SIZE: 6 * 1024 * 1024,
        CONFIG_MAX_BATCH_SIZE: 7,
    }

    @classmethod
    def get_plugin_name(cls) -> str:
        return "PicEval"

    @classmethod
    def get_plugin_description(cls) -> str:
        return "send random selection of pic, let group member to evaluate the pic"

    @classmethod
    def get_plugin_version(cls) -> str:
        return "0.0.4"

    @classmethod
    def get_plugin_author(cls) -> str:
        return "whth"

    def install(self):
        from colorama import Fore
        from graia.ariadne.message.chain import MessageChain
        from graia.ariadne.model import Group
        from graia.ariadne.message.parser.base import ContainKeyword
        from graia.ariadne.message.element import Image, MultimediaElement, Plain
        from graia.ariadne.util.cooldown import CoolDown
        from graia.ariadne.event.message import GroupMessage, ActiveGroupMessage, MessageEvent
        from graia.ariadne.exception import UnknownTarget
        from modules.file_manager import download_file, compress_image_max_vol
        from .select import Selector
        from .evaluate import Evaluate
        from .img_manager import ImageRegistry

        img_registry = ImageRegistry(
            f"{get_pwd()}/images_registry.json",
            recycle_folder=self._config_registry.get_config(self.CONFIG_RECYCLE_FOLDER),
        )
        ignored: List[str] = self._config_registry.get_config(self.CONFIG_PICTURE_IGNORED_DIRS)
        cache_dir_path: str = self._config_registry.get_config(self.CONFIG_PICTURE_CACHE_DIR_PATH)
        asset_dir_paths: List[str] = self._config_registry.get_config(self.CONFIG_PICTURE_ASSET_PATH)
        store_dir_path: str = self._config_registry.get_config(self.CONFIG_STORE_DIR_PATH)
        pathlib.Path(store_dir_path).mkdir(parents=True, exist_ok=True)
        level_resolution: int = self._config_registry.get_config(self.CONFIG_LEVEL_RESOLUTION)
        max_batch_size: int = self._config_registry.get_config(self.CONFIG_MAX_BATCH_SIZE)

        selector: Selector = Selector(asset_dirs=asset_dir_paths, cache_dir=cache_dir_path, ignore_dirs=ignored)
        evaluator: Evaluate = Evaluate(store_dir_path=store_dir_path, level_resolution=level_resolution)

        from graia.ariadne import Ariadne

        @self.receiver(GroupMessage)
        async def evaluate(app: Ariadne, group: Group, message: MessageChain, event: MessageEvent):
            """
            Asynchronous function that evaluates a message in a group chat and assigns a score to it.

            Args:
                group (Group): The group where the message is being evaluated.
                message (MessageChain): The message that is being evaluated.
                event (MessageEvent): The event associated with the message.

            Returns:
                None

            Raises:
                UnknownTarget: If the origin message cannot be found.

            Notes:
                - This function is decorated with `@bord_cast.receiver`.
                - The message is evaluated based on the score provided in the message.
                - The origin message is retrieved using the `ariadne_app.get_message_from_id` method.
                - The evaluated message can be an image or a multimedia element.
                - The evaluated message is marked with the assigned score using the `evaluator.mark` method.
                - The evaluated message and its score are sent as a group message using the `ariadne_app.send_group_message` method.
            """
            if not hasattr(event.quote, "origin"):
                return
            try:
                score = int(str(message.get(Plain, 1)[0]))
            except ValueError:
                return
            try:
                origin_message: GroupMessage = await app.get_message_from_id(message=event.quote.id, target=group)
            except UnknownTarget:
                await app.send_group_message(group, "a, 这次不行")
                return
            origin_chain: MessageChain = origin_message.message_chain
            if Image in origin_chain:
                print("FOUND IMAGE")
                path = await download_file(origin_chain.get(Image, 1)[0].url, cache_dir_path)
            elif MultimediaElement in origin_chain:
                print("FOUND MULTIMEDIA")
                path = await download_file(origin_chain.get(MultimediaElement, 1)[0].url, cache_dir_path)
            else:
                return

            print(f"{Fore.GREEN}eval {score} at {path}")
            evaluator.mark(path, score)
            await app.send_group_message(group, f"Evaluated pic as {score}")

        activate_keyword: str = self._config_registry.get_config(self.CONFIG_RAND_KEYWORD)
        reg = re.compile(rf"^{activate_keyword}(?:$|\s+(\d+)$)")

        @self.receiver(
            GroupMessage,
            decorators=[
                ContainKeyword(keyword=activate_keyword),
            ],
            dispatchers=[CoolDown(5)],
        )
        async def rand_picture(app: Ariadne, group: Group, message: MessageChain):
            """
            An asynchronous function that is decorated as a receiver for the "GroupMessage" event.
            This function is triggered when a group message is received and contains a keyword
            specified in the configuration.
            It selects a random picture using the "selector"
            object, compresses the image to a specified maximum file size using the
            "compress_image_max_vol" function, and sends the compressed image to the group using
            the "ariadne_app.send_group_message" function.

            Parameters:
                group (Group): The group object representing the group where the message was
                received.

            Returns:
                None
            """

            string: str = str(message)
            matches = re.match(reg, string)
            if not matches:
                return
            match_groups = matches.groups()
            loop_len = int(match_groups[0]) if match_groups[0] else 1
            loop_len = loop_len if loop_len <= max_batch_size else max_batch_size
            print(f"{Fore.BLUE}Loop for {loop_len}{Fore.RESET}")
            for _ in range(loop_len):
                picture = selector.random_select()

                output_path = f"{cache_dir_path}/{os.path.basename(picture)}"
                quality = compress_image_max_vol(
                    picture, output_path, self._config_registry.get_config(self.CONFIG_MAX_FILE_SIZE)
                )
                print(f"Compress to {quality}")

                await app.send_group_message(group, Image(path=output_path) + Plain(picture))

        @self.receiver(ActiveGroupMessage)
        async def watcher(message: ActiveGroupMessage):
            chain = message.message_chain
            plain_ele = chain.get(Plain, 1)
            if not plain_ele:
                return
            file_path: str = plain_ele[0].text
            if message.id != -1 and Image in chain and os.path.exists(file_path):
                img_registry.register(message.id, file_path)

                print(f"registered {message.id}, Current len = {len(img_registry.images_registry)}")

        @self.receiver(
            GroupMessage,
            decorators=[
                ContainKeyword("rm"),
            ],
        )
        async def rm_picture(app: Ariadne, group: Group, event: MessageEvent):
            if not hasattr(event.quote, "origin"):
                return
            success = img_registry.remove(event.quote.id, save=True)
            await app.send_group_message(group, f"Remove id-{event.quote.id}\nSuccess = {success}")
