import types

# ================================
# Customization of applevel tests
# ================================
#
# The various AppTestFoo classes are automatically collected and generated by
# make_hpy_apptest below. Additionally, it is possible to customize the body
# of the generated AppTest* classes by creating extra_AppTest* classes below

# to skip a specific test, you can do the following:
## class extra_AppTestBasic:
##     def test_exception_occurred(self):
##         import pytest
##         pytest.skip('fixme')

class extra_AppTestCPythonCompatibility:
    USE_CPYEXT = True

# ========================================================================
# pytest hooks to automatically generate AppTests from HPy vendored tests
# ========================================================================

def pytest_pycollect_makeitem(collector, name, obj):
    config = collector.config
    if config.getoption('runappdirect') or config.getoption('direct_apptest'):
        return
    from pypy.tool.pytest.apptest import AppClassCollector
    from pypy.module._hpy_universal.test._vendored.support import HPyTest
    if (collector.istestclass(obj, name) and
            issubclass(obj, HPyTest) and
            not name.startswith('App')):
        appname = make_hpy_apptest(collector, name, obj)
        return AppClassCollector(appname, parent=collector)

def pytest_ignore_collect(path, config):
    if path == config.rootdir.join('pypy', 'module', '_hpy_universal', 'test',
                                   '_vendored', 'test_support.py'):
        return True

def make_hpy_apptest(collector, name, cls):
    """
    Automatically create HPy AppTests from the _vendored tests.
    This is more or less equivalent of doing the following:

        from pypy.module._hpy_universal.test._vendored.test_basic import TestBasic
        class AppTestBasic(HPyAppTest, TestBasic):
            pass

    """
    from pypy.module._hpy_universal.test.support import HPyAppTest, HPyCPyextAppTest
    appname = 'App' + name
    #
    # if there is a global extra_AppTestFoo, copy its dictionary into the
    # AppTestFoo type which we are going to create
    extra = globals().get('extra_' + appname)
    if extra:
        d = extra.__dict__
    else:
        d = {}
    #
    # the original HPy test classes might contain helper methods such as
    # TestParseItem.make_parse_item: to make them available inside AppTests,
    # we need to prefix them with w_. Here it's a generic way to make
    # available at applevel all the non-test methods which are found
    for name, value in cls.__dict__.iteritems():
        if (not name.startswith('test_') and
            not name.startswith('__') and
            isinstance(value, types.FunctionType)):
            d['w_%s' % name] = value
    #
    # cpyext tests need a different base class
    use_cpyext = getattr(extra, 'USE_CPYEXT', False)
    if use_cpyext:
        bases = (HPyCPyextAppTest, cls)
    else:
        bases = (HPyAppTest, cls)
    #
    # finally, we can create the new AppTest class
    appcls = type(appname, bases, d)
    setattr(collector.obj, appname, appcls)
    return appname
