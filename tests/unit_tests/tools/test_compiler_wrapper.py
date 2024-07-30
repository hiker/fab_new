##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler wrapper implementation.
'''

from pathlib import Path, PosixPath
from unittest import mock

import pytest

from fab.tools import (Category, CCompiler,
                       Gcc, Gfortran, Icc, Ifort,
                       CompilerWrapper, Mpicc, Mpif90, ToolRepository)


def test_compiler_check_available():
    '''Check if check_available works as expected. The compiler class
    uses internally get_version to test if a compiler works or not.
    '''
    cc = CCompiler("gcc", "gcc", "gnu")
    # The compiler uses get_version to check if it is available.
    # First simulate a successful run:
    with mock.patch.object(cc, "get_version", returncode=123):
        assert cc.check_available()

    # Now test if get_version raises an error
    with mock.patch.object(cc, "get_version", side_effect=RuntimeError("")):
        assert not cc.check_available()


def test_compiler_hash():
    '''Test the hash functionality.'''
    cc = CCompiler("gcc", "gcc", "gnu")
    with mock.patch.object(cc, "_version", 567):
        hash1 = cc.get_hash()
        assert hash1 == 4646426180

    # A change in the version number must change the hash:
    with mock.patch.object(cc, "_version", 89):
        hash2 = cc.get_hash()
        assert hash2 != hash1

    # A change in the name must change the hash, again:
    cc._name = "new_name"
    hash3 = cc.get_hash()
    assert hash3 not in (hash1, hash2)


def test_compiler_wrapper_syntax_only():
    '''Tests handling of syntax only flags in wrapper. In case of testing
    syntax only for a C compiler an exception must be raised.'''
    mpif90 = ToolRepository().get_tool(Category.FORTRAN_COMPILER,
                                       "mpif90-gfortran")
    assert mpif90.has_syntax_only

    mpicc = ToolRepository().get_tool(Category.C_COMPILER, "mpicc-gcc")
    with pytest.raises(RuntimeError) as err:
        _ = mpicc.has_syntax_only
    assert "'gcc' has no has_syntax_only" in str(err.value)


def test_compiler_module_output():
    '''Tests handling of module output_flags in wrapper. In case of testing
    this with a C compiler, an exception must be raised.'''
    mpif90 = ToolRepository().get_tool(Category.FORTRAN_COMPILER,
                                       "mpif90-gfortran")
    mpif90.set_module_output_path("/somewhere")
    assert mpif90._compiler._module_output_path == "/somewhere"

    mpicc = ToolRepository().get_tool(Category.C_COMPILER, "mpicc-gcc")
    with pytest.raises(RuntimeError) as err:
        mpicc.set_module_output_path("/tmp")
    assert "'gcc' has no 'set_module_output_path' function" in str(err.value)


def test_compiler_with_add_args():
    '''Tests that additional arguments are handled as expected.'''
    mpif90 = ToolRepository().get_tool(Category.FORTRAN_COMPILER,
                                       "mpif90-gfortran")
    mpif90.set_module_output_path("/module_out")
    mpif90._compiler.run = mock.MagicMock()
    with pytest.warns(UserWarning, match="Removing managed flag"):
        mpif90.compile_file(Path("a.f90"), "a.o", add_flags=["-J/b", "-O3"],
                            openmp=False, syntax_only=True)
    # Notice that "-J/b" has been removed
    mpif90._compiler.run.assert_called_with(
        cwd=PosixPath('.'), additional_parameters=['-c', "-O3",
                                                   '-fsyntax-only',
                                                   '-J', '/module_out',
                                                   'a.f90', '-o', 'a.o'])
    with pytest.warns(UserWarning,
                      match="explicitly provided. OpenMP should be enabled in "
                            "the BuildConfiguration"):
        mpif90.compile_file(Path("a.f90"), "a.o",
                            add_flags=["-fopenmp", "-O3"],
                            openmp=True, syntax_only=True)


def test_flags():
    '''Tests that flags set in the base compiler will be accessed in the
    wrapper.'''
    gcc = Gcc()
    mpicc = Mpicc(gcc)
    assert gcc.flags == []
    assert mpicc.flags == []
    # Setting flags in gcc must become visible in the wrapper compiler:
    gcc.add_flags(["-a", "-b"])
    assert gcc.flags == ["-a", "-b"]
    assert mpicc.flags == ["-a", "-b"]


def test_mpi_gcc():
    '''Tests the MPI enables gcc class.'''
    mpi_gcc = Mpicc(Gcc())
    assert mpi_gcc.name == "mpicc-gcc"
    assert str(mpi_gcc) == "Mpicc(gcc)"
    assert isinstance(mpi_gcc, CompilerWrapper)
    assert mpi_gcc.category == Category.C_COMPILER
    assert mpi_gcc.mpi


def test_mpi_gfortran():
    '''Tests the MPI enabled gfortran class.'''
    mpi_gfortran = Mpif90(Gfortran())
    assert mpi_gfortran.name == "mpif90-gfortran"
    assert str(mpi_gfortran) == "Mpif90(gfortran)"
    assert isinstance(mpi_gfortran, CompilerWrapper)
    assert mpi_gfortran.category == Category.FORTRAN_COMPILER
    assert mpi_gfortran.mpi


def test_mpi_icc():
    '''Tests the MPI enabled icc class.'''
    mpi_icc = Mpicc(Icc())
    assert mpi_icc.name == "mpicc-icc"
    assert str(mpi_icc) == "Mpicc(icc)"
    assert isinstance(mpi_icc, CompilerWrapper)
    assert mpi_icc.category == Category.C_COMPILER
    assert mpi_icc.mpi


def test_mpi_ifort():
    '''Tests the MPI enabled ifort class.'''
    mpi_ifort = Mpif90(Ifort())
    assert mpi_ifort.name == "mpif90-ifort"
    assert str(mpi_ifort) == "Mpif90(ifort)"
    assert isinstance(mpi_ifort, CompilerWrapper)
    assert mpi_ifort.category == Category.FORTRAN_COMPILER
    assert mpi_ifort.mpi
