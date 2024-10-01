##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the PSyclone implementation.
'''

from importlib import reload
from unittest import mock

import pytest

from fab.tools import (Category, Psyclone)


def get_mock_result(version_info: str) -> mock.Mock:
    '''Returns a mock PSyclone object that will return
    the specified str as version info.

    :param version_info: the simulated output of psyclone --version
        The leading "PSyclone version: " will be added automatically.
    '''
    # The return of subprocess run has an attribute 'stdout',
    # that returns the stdout when its `decode` method is called.
    # So we mock stdout, then put this mock_stdout into the mock result:
    mock_stdout = mock.Mock(decode=lambda: f"PSyclone version: {version_info}")
    mock_result = mock.Mock(stdout=mock_stdout, returncode=0)
    return mock_result


def test_psyclone_constructor():
    '''Test the PSyclone constructor.'''
    psyclone = Psyclone()
    assert psyclone.category == Category.PSYCLONE
    assert psyclone.name == "psyclone"
    assert psyclone.exec_name == "psyclone"
    # pylint: disable=use-implicit-booleaness-not-comparison
    assert psyclone.flags == []


def test_psyclone_check_available_2_4_0():
    '''Tests the is_available functionality with version 2.4.0.
    We get only one call.
    '''
    psyclone = Psyclone()

    mock_result = get_mock_result("2.4.0")
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert psyclone.check_available()
    tool_run.assert_called_once_with(
        ["psyclone", "--version", mock.ANY], capture_output=True,
        env=None, cwd=None, check=False)


def test_psyclone_check_available_2_5_0():
    '''Tests the is_available functionality with PSyclone 2.5.0.
    We get two calls. First version, then check if nemo API exists
    '''
    psyclone = Psyclone()

    mock_result = get_mock_result("2.5.0")
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert psyclone.check_available()
    tool_run.assert_any_call(
        ["psyclone", "--version", mock.ANY], capture_output=True,
        env=None, cwd=None, check=False)
    tool_run.assert_any_call(
        ["psyclone", "-api", "nemo", mock.ANY], capture_output=True,
        env=None, cwd=None, check=False)

    # Test behaviour if a runtime error happens:
    with mock.patch("fab.tools.tool.Tool.run",
                    side_effect=RuntimeError("")) as tool_run:
        with pytest.warns(UserWarning,
                          match="Unexpected version information "
                                "for PSyclone: ''."):
            assert not psyclone.check_available()


def test_psyclone_check_available_after_2_5_0():
    '''Tests the is_available functionality with releases after 2.5.0.
    We get two calls. First version, then check if nemo API exists
    '''
    psyclone = Psyclone()

    # We detect the dummy version '2.5.0.1' if psyclone reports 2.5.0
    # but the command line option "-api nemo" is not accepted.
    # So we need to return two results from our mock objects: first
    # success for version 2.5.0, then a failure with an appropriate
    # error message:
    mock_result1 = get_mock_result("2.5.0")
    mock_result2 = get_mock_result("Unsupported PSyKAL DSL / "
                                   "API 'nemo' specified")
    mock_result2.returncode = 1

    # "Unsupported PSyKAL DSL / API 'nemo' specified"
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result1) as tool_run:
        tool_run.side_effect = [mock_result1, mock_result2]
        assert psyclone.check_available()
        assert psyclone._version == (2, 5, 0, 1)


def test_psyclone_check_available_errors():
    '''Test various errors that can happen in check_available.
    '''
    psyclone = Psyclone()
    with mock.patch('fab.tools.tool.subprocess.run',
                    side_effect=FileNotFoundError("ERR")):
        assert not psyclone.check_available()

    psyclone = Psyclone()
    mock_result = get_mock_result("NOT_A_NUMBER.4.0")
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result):
        with pytest.warns(UserWarning,
                          match="Unexpected version information for PSyclone: "
                                "'PSyclone version: NOT_A_NUMBER.4.0'"):
            assert not psyclone.check_available()
    # Also check that we can't call process if PSyclone is not available.
    psyclone._is_available = False
    config = mock.Mock()
    with pytest.raises(RuntimeError) as err:
        psyclone.process(config, "x90file")
    assert "PSyclone is not available" in str(err.value)


def test_psyclone_processing_errors_without_api():
    '''Test all processing errors in PSyclone if no API is specified.'''

    psyclone = Psyclone()
    psyclone._is_available = True
    config = mock.Mock()

    # No API --> we need transformed file, but not psy or alg:
    with pytest.raises(RuntimeError) as err:
        psyclone.process(config, "x90file", api=None, psy_file="psy_file")
    assert ("PSyclone called without api, but psy_file is specified"
            in str(err.value))
    with pytest.raises(RuntimeError) as err:
        psyclone.process(config, "x90file", api=None, alg_file="alg_file")
    assert ("PSyclone called without api, but alg_file is specified"
            in str(err.value))
    with pytest.raises(RuntimeError) as err:
        psyclone.process(config, "x90file", api=None)
    assert ("PSyclone called without api, but transformed_file is not "
            "specified" in str(err.value))


@pytest.mark.parametrize("api", ["dynamo0.3", "lfric"])
def test_psyclone_processing_errors_with_api(api):
    '''Test all processing errors in PSyclone if an API is specified.'''

    psyclone = Psyclone()
    psyclone._is_available = True
    config = mock.Mock()

    # No API --> we need transformed file, but not psy or alg:
    with pytest.raises(RuntimeError) as err:
        psyclone.process(config, "x90file", api=api, psy_file="psy_file")
    assert (f"PSyclone called with api '{api}', but no alg_file is specified"
            in str(err.value))
    with pytest.raises(RuntimeError) as err:
        psyclone.process(config, "x90file", api=api, alg_file="alg_file")
    assert (f"PSyclone called with api '{api}', but no psy_file is specified"
            in str(err.value))
    with pytest.raises(RuntimeError) as err:
        psyclone.process(config, "x90file", api=api,
                         psy_file="psy_file", alg_file="alg_file",
                         transformed_file="transformed_file")
    assert (f"PSyclone called with api '{api}' and transformed_file"
            in str(err.value))


@pytest.mark.parametrize("version", ["2.4.0", "2.5.0"])
@pytest.mark.parametrize("api", [("dynamo0.3", "dynamo0.3"),
                                 ("lfric", "dynamo0.3"),
                                 ("gocean1.0", "gocean1.0"),
                                 ("gocean", "gocean1.0")
                                 ])
def test_psyclone_process_api_old_psyclone(api, version):
    '''Test running 'old style' PSyclone (2.5.0 and earlier) with the old API
    names (dynamo0.3 and gocean1.0). Also check that the new API names will
    be accepted, but are mapped to the old style names. The 'api' parameter
    contains the input api, and expected output API.
    '''
    api_in, api_out = api
    psyclone = Psyclone()
    mock_result = get_mock_result(version)
    transformation_function = mock.Mock(return_value="script_called")
    config = mock.Mock()
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        psyclone.process(config=config,
                         api=api_in,
                         x90_file="x90_file",
                         psy_file="psy_file",
                         alg_file="alg_file",
                         transformation_script=transformation_function,
                         kernel_roots=["root1", "root2"],
                         additional_parameters=["-c", "psyclone.cfg"])
    tool_run.assert_called_with(
        ['psyclone', '-api', api_out, '-opsy', 'psy_file',
         '-oalg', 'alg_file', '-l', 'all', '-s', 'script_called', '-c',
         'psyclone.cfg', '-d', 'root1', '-d', 'root2', 'x90_file'],
        capture_output=True, env=None, cwd=None, check=False)


@pytest.mark.parametrize("version", ["2.4.0", "2.5.0"])
def test_psyclone_process_no_api_old_psyclone(version):
    '''Test running old-style PSyclone (2.5.0 and earlier) when requesting
    to transform existing files by not specifying an API. We need to add
    the flags `-api nemo` in this case for older PSyclone versions.
    '''
    psyclone = Psyclone()
    mock_result = get_mock_result(version)
    transformation_function = mock.Mock(return_value="script_called")
    config = mock.Mock()

    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        psyclone.process(config=config,
                         api="",
                         x90_file="x90_file",
                         transformed_file="psy_file",
                         transformation_script=transformation_function,
                         kernel_roots=["root1", "root2"],
                         additional_parameters=["-c", "psyclone.cfg"])
    tool_run.assert_called_with(
        ['psyclone', '-api', 'nemo', '-opsy', 'psy_file', '-l', 'all',
         '-s', 'script_called', '-c',
         'psyclone.cfg', '-d', 'root1', '-d', 'root2', 'x90_file'],
        capture_output=True, env=None, cwd=None, check=False)


@pytest.mark.parametrize("version", ["2.4.0", "2.5.0"])
def test_psyclone_process_nemo_api_old_psyclone(version):
    '''Test running old-style PSyclone (2.5.0 and earlier) when requesting
    to transform existing files by specifying the nemo api.
    '''

    psyclone = Psyclone()
    mock_result = get_mock_result(version)
    transformation_function = mock.Mock(return_value="script_called")
    config = mock.Mock()

    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        psyclone.process(config=config,
                         api="nemo",
                         x90_file="x90_file",
                         transformed_file="psy_file",
                         transformation_script=transformation_function,
                         kernel_roots=["root1", "root2"],
                         additional_parameters=["-c", "psyclone.cfg"])
    tool_run.assert_called_with(
        ['psyclone', '-api', 'nemo', '-opsy', 'psy_file', '-l', 'all',
         '-s', 'script_called', '-c',
         'psyclone.cfg', '-d', 'root1', '-d', 'root2', 'x90_file'],
        capture_output=True, env=None, cwd=None, check=False)


@pytest.mark.parametrize("api", [("dynamo0.3", "lfric"),
                                 ("lfric", "lfric"),
                                 ("gocean1.0", "gocean"),
                                 ("gocean", "gocean")
                                 ])
def test_psyclone_process_api_new__psyclone(api):
    '''Test running the new PSyclone version. Since this version is not
    yet released, we use the Fab internal version number 2.5.0.1 for
    now. It uses new API names, and we need to check that the old style
    names are converted to the new names.
    '''
    api_in, api_out = api
    psyclone = Psyclone()
    mock_result = get_mock_result("2.5.0.1")
    transformation_function = mock.Mock(return_value="script_called")
    config = mock.Mock()
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        psyclone.process(config=config,
                         api=api_in,
                         x90_file="x90_file",
                         psy_file="psy_file",
                         alg_file="alg_file",
                         transformation_script=transformation_function,
                         kernel_roots=["root1", "root2"],
                         additional_parameters=["-c", "psyclone.cfg"])
    tool_run.assert_called_with(
        ['psyclone', '--psykal-dsl', api_out, '-opsy', 'psy_file',
         '-oalg', 'alg_file', '-l', 'all', '-s', 'script_called', '-c',
         'psyclone.cfg', '-d', 'root1', '-d', 'root2', 'x90_file'],
        capture_output=True, env=None, cwd=None, check=False)


def test_psyclone_process_no_api_new_psyclone():
    '''Test running the new PSyclone version without an API. Since this
    version is not yet released, we use the Fab internal version number
    2.5.0.1 for now.
    '''
    psyclone = Psyclone()
    mock_result = get_mock_result("2.5.0.1")
    transformation_function = mock.Mock(return_value="script_called")
    config = mock.Mock()

    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        psyclone.process(config=config,
                         api="",
                         x90_file="x90_file",
                         transformed_file="psy_file",
                         transformation_script=transformation_function,
                         kernel_roots=["root1", "root2"],
                         additional_parameters=["-c", "psyclone.cfg"])
    tool_run.assert_called_with(
        ['psyclone', '-o', 'psy_file', '-l', 'all',
         '-s', 'script_called', '-c',
         'psyclone.cfg', '-d', 'root1', '-d', 'root2', 'x90_file'],
        capture_output=True, env=None, cwd=None, check=False)


def test_psyclone_process_nemo_api_new_psyclone():
    '''Test running PSyclone. Since this version is not yet released, we use
    the Fab internal version number 2.5.0.1 for now. This tests that
    backwards compatibility of using the nemo api works, i.e. '-api nemo' is
    just removed.
    '''
    psyclone = Psyclone()
    mock_result = get_mock_result("2.5.0.1")
    transformation_function = mock.Mock(return_value="script_called")
    config = mock.Mock()

    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        psyclone.process(config=config,
                         api="nemo",
                         x90_file="x90_file",
                         transformed_file="psy_file",
                         transformation_script=transformation_function,
                         kernel_roots=["root1", "root2"],
                         additional_parameters=["-c", "psyclone.cfg"])
    tool_run.assert_called_with(
        ['psyclone', '-o', 'psy_file', '-l', 'all',
         '-s', 'script_called', '-c',
         'psyclone.cfg', '-d', 'root1', '-d', 'root2', 'x90_file'],
        capture_output=True, env=None, cwd=None, check=False)


def test_type_checking_import():
    '''PSyclone contains an import of TYPE_CHECKING to break a circular
    dependency. In order to reach 100% coverage of PSyclone, we set
    mock TYPE_CHECKING to be true and force a re-import of the module.
    TODO 314: This test can be removed once #314 is fixed.
    '''
    with mock.patch('typing.TYPE_CHECKING', True):
        # This import will not actually re-import, since the module
        # is already imported. But we need this in order to call reload:
        # pylint: disable=import-outside-toplevel
        import fab.tools.psyclone
        reload(fab.tools.psyclone)
