import py, os, sys
from pypy.conftest import gettestobjspace


currpath = py.path.local(__file__).dirpath()
test_dct = str(currpath.join("overloadsDict.so"))

space = gettestobjspace(usemodules=['cppyy'])

def setup_module(mod):
    if sys.platform == 'win32':
        py.test.skip("win32 not supported so far")
    err = os.system("cd '%s' && make overloadsDict.so" % currpath)
    if err:
        raise OSError("'make' failed (see stderr)")

class AppTestOVERLOADS:
    def setup_class(cls):
        cls.space = space
        env = os.environ
        cls.w_test_dct  = space.wrap(test_dct)
        cls.w_overloads = cls.space.appexec([], """():
            import cppyy
            return cppyy.load_reflection_info(%r)""" % (test_dct, ))

    def test01_class_based_overloads(self):
        """Test functions overloaded on different C++ clases"""

        import cppyy
        a_overload = cppyy.gbl.a_overload
        b_overload = cppyy.gbl.b_overload
        c_overload = cppyy.gbl.c_overload
        d_overload = cppyy.gbl.d_overload

        ns_a_overload = cppyy.gbl.ns_a_overload
        ns_b_overload = cppyy.gbl.ns_b_overload

        assert c_overload().get_int(a_overload()) == 42
        assert c_overload().get_int(b_overload()) == 13
        assert d_overload().get_int(a_overload()) == 42
        assert d_overload().get_int(b_overload()) == 13

        assert c_overload().get_int(ns_a_overload.a_overload()) ==  88
        assert c_overload().get_int(ns_b_overload.a_overload()) == -33

        assert d_overload().get_int(ns_a_overload.a_overload()) ==  88
        assert d_overload().get_int(ns_b_overload.a_overload()) == -33

    def test02_class_based_overloads_explicit_resolution(self):
        """Test explicitly resolved function overloads"""

        # TODO: write disp() or equivalent on methods for ol selection

        import cppyy
        a_overload = cppyy.gbl.a_overload
        b_overload = cppyy.gbl.b_overload
        c_overload = cppyy.gbl.c_overload
        d_overload = cppyy.gbl.d_overload

        ns_a_overload = cppyy.gbl.ns_a_overload

        c = c_overload()
#        raises(TypeError, c.get_int.disp, 12)
#        assert c.get_int.disp('a_overload* a')(a_overload()) == 42
#        assert c.get_int.disp('b_overload* b')(b_overload()) == 13

#        assert c_overload().get_int.disp('a_overload* a')(a_overload())  == 42
#        assert c_overload.get_int.disp('b_overload* b')(c, b_overload()) == 13

        d = d_overload()
#        assert d.get_int.disp('a_overload* a')(a_overload()) == 42
#        assert d.get_int.disp('b_overload* b')(b_overload()) == 13

        nb = ns_a_overload.b_overload()
        raises(TypeError, nb.f, c_overload())

    def test03_fragile_class_based_overloads(self):
        """Test functions overloaded on void* and non-existing classes"""

        # TODO: make Reflex generate unknown classes ...

        import cppyy
        more_overloads = cppyy.gbl.more_overloads
        aa_ol = cppyy.gbl.aa_ol
#        bb_ol = cppyy.gbl.bb_ol
        cc_ol = cppyy.gbl.cc_ol
#        dd_ol = cppyy.gbl.dd_ol

        assert more_overloads().call(aa_ol()).c_str() == "aa_ol"
#        assert more_overloads().call(bb_ol()).c_str() == "dd_ol"    # <- bb_ol has an unknown + void*
        assert more_overloads().call(cc_ol()).c_str() == "cc_ol"
#        assert more_overloads().call(dd_ol()).c_str() == "dd_ol"    # <- dd_ol has an unknown

    def test04_fully_fragile_overloads(self):
        """Test that unknown* is preferred over unknown&"""

        # TODO: make Reflex generate unknown classes ...
        return

        import cppyy
        more_overloads2 = cppyy.gbl.more_overloads2
        bb_ol = cppyy.gbl.bb_ol
        dd_ol = cppyy.gbl.dd_ol

        assert more_overloads2().call(bb_ol())    == "bb_olptr"
        assert more_overloads2().call(dd_ol(), 1) == "dd_olptr"

    def test05_array_overloads(self):
        """Test functions overloaded on different arrays"""

        # TODO: buffer to pointer interface
        return

        import cppyy
        c_overload = cppyy.gbl.c_overload

        from array import array

        ai = array('i', [525252])
        assert c_overload().get_int(ai) == 525252
        assert d_overload().get_int(ai) == 525252

        ah = array('h', [25])
        assert c_overload().get_int(ah) == 25
        assert d_overload().get_int(ah) == 25

    def test06_double_int_overloads(self):
        """Test overloads on int/doubles"""

        import cppyy
        more_overloads = cppyy.gbl.more_overloads

#        assert more_overloads().call(1).c_str()   == "int"
#        assert more_overloads().call(1.).c_str()  == "double"
        assert more_overloads().call1(1).c_str()  == "int"
        assert more_overloads().call1(1.).c_str() == "double"
