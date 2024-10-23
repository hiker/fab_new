##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This file contains the ToolRepository class.
'''

# We can't declare _singleton and __new__() using ToolRepository, but
# it is allowed if we use this import:
from __future__ import annotations

import logging
from typing import cast, Optional

from fab.tools.tool import Tool
from fab.tools.category import Category
from fab.tools.compiler import Compiler
from fab.tools.compiler_wrapper import CrayCc, CrayFtn, Mpif90, Mpicc
from fab.tools.linker import Linker
from fab.tools.versioning import Fcm, Git, Subversion
from fab.tools import (Ar, Cpp, CppFortran, Craycc, Crayftn,
                       Gcc, Gfortran, Icc, Icx, Ifort, Ifx,
                       Nvc, Nvfortran, Psyclone, Rsync, Shell)


class ToolRepository(dict):
    '''This class implements the tool repository. It stores a list of
    tools for various categories. For each compiler, it will automatically
    create a tool called "linker-{compiler-name}" which can be used for
    linking with the specified compiler.
    '''

    _singleton: None | ToolRepository = None

    def __new__(cls) -> ToolRepository:
        '''Singleton access. Changes the value of _singleton so that the
        constructor can verify that it is indeed called from here.
        '''
        if not cls._singleton:
            cls._singleton = super().__new__(cls)

        return cls._singleton

    def __init__(self):
        # Note that in this singleton pattern the constructor is called each
        # time the instance is requested (since we overwrite __new__). But
        # we only want to initialise the instance once, so let the constructor
        # not do anything if the singleton already exists:
        # pylint: disable=too-many-locals
        if ToolRepository._singleton:
            return

        self._logger = logging.getLogger(__name__)
        super().__init__()

        # Create the list that stores all tools for each category:
        for category in Category:
            self[category] = []

        # Add the FAB default tools:
        # TODO: sort the defaults so that they actually work (since not all
        # tools FAB knows about are available). For now, disable Fpp (by not
        # adding it). IF someone actually uses it it can added.
        for cls in [Craycc, Crayftn,
                    Gcc, Gfortran,
                    Icc, Icx, Ifort, Ifx,
                    Nvc, Nvfortran,
                    Cpp, CppFortran,
                    Ar, Fcm, Git, Psyclone, Rsync, Subversion]:
            self.add_tool(cls())

        # Add the common shells. While Fab itself does not need this,
        # it is a very convenient tool for user configuration (e.g. to
        # query nc-config etc)
        for shell_name in ["bash", "sh", "ksh", "dash"]:
            self.add_tool(Shell(shell_name))
            self.get_tool(Category.SHELL, shell_name)

        # Now create the potential mpif90 and Cray ftn wrapper
        all_fc = self[Category.FORTRAN_COMPILER][:]
        for fc in all_fc:
            mpif90 = Mpif90(fc)
            self.add_tool(mpif90)
            # I assume cray has (besides cray) only support for gfortran/ifort
            if fc.name in ["gfortran", "ifort"]:
                crayftn = CrayFtn(fc)
                self.add_tool(crayftn)

        # Now create the potential mpicc and Cray cc wrapper
        all_cc = self[Category.C_COMPILER][:]
        for cc in all_cc:
            mpicc = Mpicc(cc)
            self.add_tool(mpicc)
            # I assume cray has (besides cray) only support for gfortran/ifort
            if cc.name in ["gcc", "icc"]:
                craycc = CrayCc(cc)
                self.add_tool(craycc)

    def add_tool(self, tool: Tool):
        '''Creates an instance of the specified class and adds it
        to the tool repository.

        :param cls: the tool to instantiate.
        '''

        # We do not test if a tool is actually available. The ToolRepository
        # contains the tools that FAB knows about. It is the responsibility
        # of the ToolBox to make sure only available tools are added.
        self[tool.category].append(tool)

        # If we have a compiler, add the compiler as linker as well
        if tool.is_compiler:
            tool = cast(Compiler, tool)
            linker = Linker(name=f"linker-{tool.name}", compiler=tool)
            self[linker.category].append(linker)

    def get_tool(self, category: Category, name: str) -> Tool:
        ''':returns: the tool with a given name in the specified category.

        :param category: the name of the category in which to look
            for the tool.
        :param name: the name of the tool to find.

        :raises KeyError: if there is no tool in this category.
        :raises KeyError: if no tool in the given category has the
            requested name.
        '''

        if category not in self:
            raise KeyError(f"Unknown category '{category}' "
                           f"in ToolRepository.get_tool().")
        all_tools = self[category]
        for tool in all_tools:
            if tool.name == name:
                return tool
        raise KeyError(f"Unknown tool '{name}' in category '{category}' "
                       f"in ToolRepository.")

    def set_default_compiler_suite(self, suite: str):
        '''Sets the default for linker and compilers to be of the
        given compiler suite.

        :param suite: the name of the compiler suite to make the default.
        '''
        for category in [Category.FORTRAN_COMPILER, Category.C_COMPILER,
                         Category.LINKER]:
            # Now sort the tools in this category to have all tools with the
            # right suite at the front. We use the stable sorted function with
            # the key being tool.suite != suite --> all tools with the right
            # suite use False as key, all other tools True. Since False < True
            # this results in all suite tools to be at the front of the list
            self[category] = sorted(self[category],
                                    key=lambda x: x.suite != suite)
            if len(self[category]) > 0 and self[category][0].suite != suite:
                raise RuntimeError(f"Cannot find '{category}' "
                                   f"in the suite '{suite}'.")

    def get_default(self, category: Category,
                    mpi: Optional[bool] = None):
        '''Returns the default tool for a given category. For most tools
        that will be the first entry in the list of tools. The exception
        are compilers and linker: in this case it must be specified if
        MPI support is required or not. And the default return will be
        the first tool that either supports MPI or not.

        :param category: the category for which to return the default tool.
        :param mpi: if a compiler or linker is required that supports MPI.

        :raises KeyError: if the category does not exist.
        :raises RuntimeError: if no compiler/linker is found with the
            requested level of MPI support (yes or no).
        '''

        if not isinstance(category, Category):
            raise RuntimeError(f"Invalid category type "
                               f"'{type(category).__name__}'.")

        # If not a compiler or linker, return the first tool
        if not category.is_compiler and category != Category.LINKER:
            return self[category][0]

        if not isinstance(mpi, bool):
            raise RuntimeError(f"Invalid or missing mpi specification "
                               f"for '{category}'.")

        for tool in self[category]:
            # If the tool supports/does not support MPI, return the first one
            if mpi == tool.mpi:
                return tool

        # Don't bother returning an MPI enabled tool if no-MPI is requested -
        # that seems to be an unlikely scenario.
        raise RuntimeError(f"Could not find '{category}' that supports MPI.")
