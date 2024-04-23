##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This file contains the ToolRepository class.
'''

# We can't declare _singleton and get() using ToolRepository, but
# it is allowed if we use this import:
from __future__ import annotations

import logging
from typing import Any, Type

from fab.newtools import (Categories, Cpp, CppFortran, Fpp, Gcc, Gfortran,
                          Icc, Ifort, Linker)


class ToolRepository(dict):
    '''This class implements the tool repository. It stores a list of
    tools for various categories.
    '''

    _singleton: None | ToolRepository = None

    @staticmethod
    def get() -> ToolRepository | Any:
        '''Singleton access. Changes the value of _singleton so that the
        constructor can verify that it is indeed called from here.
        '''
        if ToolRepository._singleton is None:
            ToolRepository._singleton = "FROM_GET"
            ToolRepository._singleton = ToolRepository()
        return ToolRepository._singleton

    def __init__(self):
        # Check if the constructor is called from 'get':
        if ToolRepository._singleton != "FROM_GET":
            raise RuntimeError("You must use 'ToolRepository.get()' to get "
                               "the singleton instance.")
        self._logger = logging.getLogger(__name__)
        super().__init__()

        # Add the FAB default tools:
        for cls in [Gcc, Icc, Gfortran, Ifort, Fpp, Cpp, CppFortran]:
            self.add_tool(cls)
        self[Categories.LINKER] = [
            Linker(compiler=self.get_default(Categories.FORTRAN_COMPILER))]

    def add_tool(self, cls: Type[Any]):
        '''Creates an instance of the specified class and adds it
        to the tool repository.
        :param cls: the tool to instantiate.
        '''

        # Note that we cannot declare `cls` to be `Type[Tool]`, since the
        # Tool constructor requires arguments, but the classes used here are
        # derived from Tool which do not require any arguments (e.g. Ifort)

        tool = cls()
        if not tool.is_available:
            self._logger.debug(f"Tool {tool.name} is not available - ignored.")
            return
        if tool.category in self:
            self[tool.category].append(tool)
        else:
            self[tool.category] = [tool]

    def get_tool(self, category: Categories, name: str):
        '''Returns the tool with a given name in the specified category.

        :param category: the name of the category in which to look
            for the tool.
        :param name: the name of the tool to find.

        :raises KeyError: if the category is not known.
        :raises KeyError: if no tool in the given category has the
            requested name.
        '''

        if category not in self:
            raise KeyError(f"Unknown category '{category}' "
                           f"in ToolRepository.get.")
        all_tools = self[category]
        for tool in all_tools:
            if tool.name == name:
                return tool
        raise KeyError(f"Unknown tool '{name}' in category '{category}' "
                       f"in ToolRepository.")

    def get_default(self, category: Categories):
        '''Returns the default tool for a given category, which is just
        the first tool in the category.

        :param category: the category for which to return the default tool.

        :raises KeyError: if the category does not exist.
        '''

        if not isinstance(category, Categories):
            raise RuntimeError(f"Invalid category type "
                               f"'{type(category).__name__}'.")
        return self[category][0]
