##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the linker implementation.
'''

from pathlib import Path
from unittest import mock
import warnings

import pytest

from fab.tools import (Category, Linker)


def test_linker(mock_c_compiler, mock_fortran_compiler):
    '''Test the linker constructor.'''

    assert mock_c_compiler.category == Category.C_COMPILER
    assert mock_c_compiler.name == "mock_c_compiler"

    linker = Linker(mock_c_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == "linker-mock_c_compiler"
    assert linker.exec_name == "mock_c_compiler.exe"
    assert linker.suite == "suite"
    assert linker.flags == []

    assert mock_fortran_compiler.category == Category.FORTRAN_COMPILER
    assert mock_fortran_compiler.name == "mock_fortran_compiler"

    linker = Linker(mock_fortran_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == "linker-mock_fortran_compiler"
    assert linker.exec_name == "mock_fortran_compiler.exe"
    assert linker.suite == "suite"
    assert linker.flags == []


def test_linker_gets_ldflags(mock_c_compiler):
    """Tests that the linker retrieves env.LDFLAGS"""
    with mock.patch.dict("os.environ", {"LDFLAGS": "-lm"}):
        linker = Linker(compiler=mock_c_compiler)
    assert "-lm" in linker.flags


def test_linker_check_available(mock_c_compiler):
    '''Tests the is_available functionality.'''

    # First test if a compiler is given. The linker will call the
    # corresponding function in the compiler:
    linker = Linker(mock_c_compiler)
    with mock.patch('fab.tools.compiler.Compiler.get_version',
                    return_value=(1, 2, 3)):
        assert linker.check_available()


def test_linker_check_unavailable(mock_c_compiler):
    '''Tests the is_available functionality.'''
    # assume the tool does not exist, check_available
    # will return False (and not raise an exception)
    linker = Linker(mock_c_compiler)
    with mock.patch('fab.tools.compiler.Compiler.get_version',
                    side_effect=RuntimeError("")):
        assert linker.check_available() is False


# ====================
# Managing lib flags:
# ====================
def test_linker_get_lib_flags(mock_linker):
    """Linker should provide a map of library names, each leading to a list of
    linker flags
    """
    # netcdf flags are built in to the mock linker
    result = mock_linker.get_lib_flags("netcdf")
    assert result == ["-lnetcdff", "-lnetcdf"]


def test_linker_get_lib_flags_unknown(mock_c_compiler):
    """Linker should raise an error if flags are requested for a library that is
    unknown
    """
    linker = Linker(compiler=mock_c_compiler)
    with pytest.raises(RuntimeError) as err:
        linker.get_lib_flags("unknown")
    assert "Unknown library name: 'unknown'" in str(err.value)


def test_linker_add_lib_flags(mock_c_compiler):
    """Linker should provide a way to add a new set of flags for a library"""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("xios", ["-L", "xios/lib", "-lxios"])

    # Make sure we can get it back. The order should be maintained.
    result = linker.get_lib_flags("xios")
    assert result == ["-L", "xios/lib", "-lxios"]


def test_linker_add_lib_flags_overwrite_defaults(mock_linker):
    """Linker should provide a way to replace the default flags for a library"""

    # Initially we have the default netcdf flags
    result = mock_linker.get_lib_flags("netcdf")
    assert result == ["-lnetcdff", "-lnetcdf"]

    # Replace them with another set of flags.
    warn_message = 'Replacing existing flags for library netcdf'
    with pytest.warns(UserWarning, match=warn_message):
        mock_linker.add_lib_flags(
            "netcdf", ["-L", "netcdf/lib", "-lnetcdf"])

    # Test that we can see our custom flags
    result = mock_linker.get_lib_flags("netcdf")
    assert result == ["-L", "netcdf/lib", "-lnetcdf"]


def test_linker_add_lib_flags_overwrite_silent(mock_linker):
    """Linker should provide the option to replace flags for a library without
    generating a warning
    """

    # Initially we have the default netcdf flags
    mock_linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    assert mock_linker.get_lib_flags("customlib") == ["-lcustom", "-jcustom"]

    # Replace them with another set of flags.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        mock_linker.add_lib_flags("customlib", ["-t", "-b"],
                                  silent_replace=True)

    # Test that we can see our custom flags
    result = mock_linker.get_lib_flags("customlib")
    assert result == ["-t", "-b"]


def test_linker_remove_lib_flags(mock_linker):
    """Linker should provide a way to remove the flags for a library"""
    mock_linker.remove_lib_flags("netcdf")

    with pytest.raises(RuntimeError) as err:
        mock_linker.get_lib_flags("netcdf")
    assert "Unknown library name: 'netcdf'" in str(err.value)


def test_linker_remove_lib_flags_unknown(mock_linker):
    """Linker should silently allow removing flags for unknown library"""
    mock_linker.remove_lib_flags("unknown")


# ====================
# Linking:
# ====================
def test_linker_c(mock_c_compiler):
    '''Test the link command line when no additional libraries are specified.'''
    linker = Linker(compiler=mock_c_compiler)
    # Add a library to the linker, but don't use it in the link step
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])

    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.link([Path("a.o")], Path("a.out"), openmp=False)
    tool_run.assert_called_with(
        ["mock_c_compiler.exe", "a.o", "-o", "a.out"],
        capture_output=True, env=None, cwd=None, check=False)


def test_linker_c_with_libraries(mock_c_compiler):
    """Test the link command line when additional libraries are specified."""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])

    with mock.patch.object(linker, "run") as link_run:
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=True)
    # The order of the 'libs' list should be maintained
    link_run.assert_called_with(
        ["-fopenmp", "a.o", "-lcustom", "-jcustom", "-o", "a.out"])


def test_linker_c_with_libraries_and_post_flags(mock_c_compiler):
    """Test the link command line when a library and additional flags are
    specified."""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    linker.add_post_lib_flags(["-extra-flag"])

    with mock.patch.object(linker, "run") as link_run:
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=False)
    link_run.assert_called_with(
        ["a.o", "-lcustom", "-jcustom", "-extra-flag", "-o", "a.out"])


def test_linker_c_with_libraries_and_pre_flags(mock_c_compiler):
    """Test the link command line when a library and additional flags are
    specified."""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    linker.add_pre_lib_flags(["-L", "/common/path/"])

    with mock.patch.object(linker, "run") as link_run:
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=False)
    link_run.assert_called_with(
        ["a.o", "-L", "/common/path/", "-lcustom", "-jcustom", "-o", "a.out"])


def test_linker_c_with_unknown_library(mock_c_compiler):
    """Test the link command raises an error when unknow libraries are
    specified.
    """
    linker = Linker(compiler=mock_c_compiler)\

    with pytest.raises(RuntimeError) as err:
        # Try to use "customlib" when we haven't added it to the linker
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=True)

    assert "Unknown library name: 'customlib'" in str(err.value)


def test_compiler_linker_add_compiler_flag(mock_c_compiler):
    '''Test that a flag added to the compiler will be automatically
    added to the link line (even if the flags are modified after creating the
    linker ... in case that the user specifies additional flags after creating
    the linker).'''

    linker = Linker(compiler=mock_c_compiler)
    mock_c_compiler.flags.append("-my-flag")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.link([Path("a.o")], Path("a.out"), openmp=False)
    tool_run.assert_called_with(
        ['mock_c_compiler.exe', '-my-flag', 'a.o', '-o', 'a.out'],
        capture_output=True, env=None, cwd=None, check=False)


def test_linker_all_flag_types(mock_c_compiler):
    """Make sure all possible sources of linker flags are used in the right
    order"""

    # Environment variables for both the compiler and linker
    # TODO: THIS IS ACTUALLY WRONG - The FFLAGS shouldn't be picked up here,
    # because the compiler already exists. It is being added twice, because
    # Linker inherits Compiler (in addition to wrapping it)
    with mock.patch.dict("os.environ", {
        "FFLAGS": "-fflag",
        "LDFLAGS": "-ldflag"
    }):
        linker = Linker(compiler=mock_c_compiler)

    mock_c_compiler.add_flags(["-compiler-flag1", "-compiler-flag2"])
    linker.add_flags(["-linker-flag1", "-linker-flag2"])
    linker.add_pre_lib_flags(["-prelibflag1", "-prelibflag2"])
    linker.add_lib_flags("customlib1", ["-lib1flag1", "lib1flag2"])
    linker.add_lib_flags("customlib2", ["-lib2flag1", "lib2flag2"])
    linker.add_post_lib_flags(["-postlibflag1", "-postlibflag2"])

    mock_result = mock.Mock(returncode=0)
    with mock.patch("fab.tools.tool.subprocess.run",
                    return_value=mock_result) as tool_run:
        linker.link([
            Path("a.o")], Path("a.out"),
            libs=["customlib2", "customlib1"],
            openmp=True)

    tool_run.assert_called_with([
        "mock_c_compiler.exe",
        "-compiler-flag1", "-compiler-flag2", "-fflag",
        "-ldflag", "-linker-flag1", "-linker-flag2",
        "-fopenmp",
        "a.o",
        "-prelibflag1", "-prelibflag2",
        "-lib2flag1", "lib2flag2",
        "-lib1flag1", "lib1flag2",
        "-postlibflag1", "-postlibflag2",
        "-o", "a.out"],
        capture_output=True, env=None, cwd=None, check=False)
