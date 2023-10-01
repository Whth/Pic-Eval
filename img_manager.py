import json
import os
import shutil
import time
from types import MappingProxyType
from typing import Optional, Dict, List


class ImageRegistry(object):  # TODO use other high performance serialize toolchain
    def __init__(self, save_path: str, recycle_folder: Optional[str] = None, max_size: Optional[int] = None) -> None:
        self._save_path = save_path
        self._max_size = max_size
        if recycle_folder:
            os.makedirs(recycle_folder, exist_ok=True)
        self._recycle_folder = recycle_folder
        self._images_registry: Dict[int, List[str, float]] = {}
        if os.path.exists(self._save_path):
            self.load()
        self._images_registry_proxy: MappingProxyType[int, List[str, float]] = MappingProxyType(self._images_registry)

    @property
    def images_registry(self) -> MappingProxyType:
        """
        Returns the mapping proxy object for the images registry.

        :return: The mapping proxy object for the images registry.
        :rtype: MappingProxyType
        """
        return self._images_registry_proxy

    def register(self, key: int, image_path: str) -> None:
        """
        Register an image in the registry.

        Args:
            key (int): The key associated with the image.
            image_path (str): The path of the image.

        Returns:
            None: This function does not return anything.
        """
        self._images_registry[key] = [image_path, time.time()]
        self.prune()
        self.save()

    def prune(self) -> None:
        """
        Prunes the images registry if the maximum size is exceeded.

        This method checks if the maximum size of the images registry is set and if the number
        of images in the registry is greater than the maximum size. If this condition is true,
        it removes the oldest images from the registry until the size is reduced to the maximum
        size.

        Parameters:
            None

        Returns:
            None
        """
        if self._max_size and len(self._images_registry) > self._max_size:
            num_to_remove = len(self._images_registry) - self._max_size
            for _ in range(num_to_remove):
                self._remove_oldest()

    def get(self, key: int) -> str:
        return self._images_registry[key][0]

    def remove(self, key: int, save: bool = False) -> bool:
        """
        Remove an image from the registry.

        Args:
            key (int): The key of the image to remove.
            save (bool, optional): Indicates whether to save the changes to the registry. Defaults to False.

        Returns:
            bool: True if the image was successfully removed, False otherwise.
        """
        if key in self._images_registry:
            file_path = self._images_registry[key][0]
            if self._recycle_folder:
                shutil.move(file_path, self._recycle_folder)
            else:
                os.remove(file_path)
            del self._images_registry[key]
            if save:
                self.save()
            return True
        return False

    def _remove_oldest(self) -> None:
        oldest_key = min(self._images_registry, key=lambda k: self._images_registry[k][1])
        del self._images_registry[oldest_key]

    def save(self) -> None:
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self._images_registry, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        with open(self._save_path, "r", encoding="utf-8") as f:
            temp: Dict[int, List[str, float]] = json.load(f)
        self._images_registry.update(temp)
