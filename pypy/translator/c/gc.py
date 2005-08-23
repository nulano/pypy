from pypy.translator.c.support import cdecl
from pypy.rpython.lltype import typeOf, Ptr, PyObject, ContainerType
from pypy.rpython.lltype import getRuntimeTypeInfo

PyObjPtr = Ptr(PyObject)

class BasicGcPolicy:
    
    def __init__(self, db):
        self.db = db

    def pyobj_incref(self, expr, T):
        if T == PyObjPtr:
            return 'Py_XINCREF(%s);' % expr
        return ''

    def pyobj_decref(self, expr, T):
        return 'Py_XDECREF(%s);' % expr

    def push_alive(self, expr, T):
        if isinstance(T, Ptr) and T._needsgc():
            if expr == 'NULL':    # hum
                return ''
            if T.TO == PyObject:
                return self.pyobj_incref(expr, T)
            else:
                return self.push_alive_nopyobj(expr, T)
        return ''

    def pop_alive(self, expr, T):
        if isinstance(T, Ptr) and T._needsgc():
            if T.TO == PyObject:
                return self.pyobj_decref(expr, T)
            else:
                return self.pop_alive_nopyobj(expr, T)
        return ''

    def pre_gc_code(self):
        return []

    def gc_startup_code(self):
        return []

class RefcountingInfo:
    deallocator = None
    static_deallocator = None

class RefcountingGcPolicy(BasicGcPolicy):

    def push_alive_nopyobj(self, expr, T):
        defnode = self.db.gettypedefnode(T.TO)
        if defnode.gcheader is not None:
            return 'if (%s) %s->%s++;' % (expr, expr, defnode.gcheader)

    def pop_alive_nopyobj(self, expr, T):
        defnode = self.db.gettypedefnode(T.TO)
        if defnode.gcheader is not None:
            dealloc = 'OP_FREE'
            if defnode.gcinfo:
                dealloc = defnode.gcinfo.deallocator or dealloc
            return 'if (%s && !--%s->%s) %s(%s);' % (expr, expr,
                                                     defnode.gcheader,
                                                     dealloc,
                                                     expr)

    def push_alive_op_result(self, opname, expr, T):
        if opname !='direct_call' and T != PyObjPtr:
            return self.push_alive(expr, T)
        return ''

    def write_barrier(self, result, newvalue, T, targetexpr):  
        decrefstmt = self.pop_alive('prev', T)
        increfstmt = self.push_alive(newvalue, T)
        if increfstmt:
            result.append(increfstmt)
        if decrefstmt:
            result.insert(0, '{ %s = %s;' % (
                cdecl(self.db.gettype(T), 'prev'),
                targetexpr))
            result.append(decrefstmt)
            result.append('}')

    def generic_dealloc(self, expr, T):
        db = self.db
        if isinstance(T, Ptr) and T._needsgc():
            line = self.pop_alive(expr, T)
            if line:
                yield line
        elif isinstance(T, ContainerType):
            defnode = db.gettypedefnode(T)
            from pypy.translator.c.node import ExtTypeOpaqueDefNode
            if isinstance(defnode, ExtTypeOpaqueDefNode):
                yield 'RPyOpaqueDealloc_%s(&(%s));' % (defnode.T.tag, expr)
            else:
                for line in defnode.visitor_lines(expr, self.generic_dealloc):
                    yield line

    def gcheader_field_name(self, defnode):
        return 'refcount'

    def common_gcheader_definition(self, defnode):
        yield 'long refcount;'

    def common_after_definition(self, defnode):
        if defnode.gcinfo:
            gcinfo = defnode.gcinfo
            if gcinfo.deallocator:
                yield 'void %s(struct %s *);' % (gcinfo.deallocator, defnode.name)

    def common_gcheader_initializationexpr(self, defnode):
        yield 'REFCOUNT_IMMORTAL,'

    def deallocator_lines(self, defnode, prefix):
        for line in defnode.visitor_lines(prefix, self.generic_dealloc):
            yield line



    # for structs

    def prepare_nested_gcstruct(self, structdefnode, INNER):
        # check here that there is enough run-time type information to
        # handle this case
        getRuntimeTypeInfo(structdefnode.STRUCT)
        getRuntimeTypeInfo(INNER)

    def struct_setup(self, structdefnode, rtti):        
        if structdefnode.gcheader:
            db = self.db
            gcinfo = structdefnode.gcinfo = RefcountingInfo()

            gcinfo.deallocator = db.namespace.uniquename('dealloc_'+structdefnode.barename)

            # are two deallocators needed (a dynamic one for DECREF, which checks
            # the real type of the structure and calls the static deallocator) ?
            if rtti is not None:
                gcinfo.static_deallocator = db.namespace.uniquename(
                    'staticdealloc_'+structdefnode.barename)
                fnptr = rtti._obj.query_funcptr
                if fnptr is None:
                    raise NotImplementedError(
                        "attachRuntimeTypeInfo(): please provide a function")
                gcinfo.rtti_query_funcptr = db.get(fnptr)
                T = typeOf(fnptr).TO.ARGS[0]
                gcinfo.rtti_query_funcptr_argtype = db.gettype(T)
            else:
                # is a deallocator really needed, or would it be empty?
                if list(self.deallocator_lines(structdefnode, '')):
                    gcinfo.static_deallocator = gcinfo.deallocator
                else:
                    gcinfo.deallocator = None

    struct_gcheader_definition = common_gcheader_definition

    struct_after_definition = common_after_definition

    def struct_implementationcode(self, structdefnode):
        if structdefnode.gcinfo:
            gcinfo = structdefnode.gcinfo
            if gcinfo.static_deallocator:
                yield 'void %s(struct %s *p) {' % (gcinfo.static_deallocator,
                                               structdefnode.name)
                for line in self.deallocator_lines(structdefnode, '(*p)'):
                    yield '\t' + line
                yield '\tOP_FREE(p);'
                yield '}'
            if gcinfo.deallocator and gcinfo.deallocator != gcinfo.static_deallocator:
                yield 'void %s(struct %s *p) {' % (gcinfo.deallocator, structdefnode.name)
                yield '\tvoid (*staticdealloc) (void *);'
                # the refcount should be 0; temporarily bump it to 1
                yield '\tp->%s = 1;' % (structdefnode.gcheader,)
                # cast 'p' to the type expected by the rtti_query function
                yield '\tstaticdealloc = %s((%s) p);' % (
                    gcinfo.rtti_query_funcptr,
                    cdecl(gcinfo.rtti_query_funcptr_argtype, ''))
                yield '\tif (!--p->%s)' % (structdefnode.gcheader,)
                yield '\t\tstaticdealloc(p);'
                yield '}'


    struct_gcheader_initialitionexpr = common_gcheader_initializationexpr

    # for arrays

    def array_setup(self, arraydefnode):
        if arraydefnode.gcheader and list(self.deallocator_lines(arraydefnode, '')):
            gcinfo = arraydefnode.gcinfo = RefcountingInfo()
            gcinfo.deallocator = self.db.namespace.uniquename('dealloc_'+arraydefnode.barename)

    array_gcheader_definition = common_gcheader_definition

    array_after_definition = common_after_definition

    def array_implementationcode(self, arraydefnode):
        if arraydefnode.gcinfo:
            gcinfo = arraydefnode.gcinfo
            if gcinfo.deallocator:
                yield 'void %s(struct %s *a) {' % (gcinfo.deallocator, arraydefnode.name)
                for line in self.deallocator_lines(arraydefnode, '(*a)'):
                    yield '\t' + line
                yield '\tOP_FREE(a);'
                yield '}'

    array_gcheader_initialitionexpr = common_gcheader_initializationexpr

    # for rtti node

    def rtti_type(self):
        return 'void (@)(void *)'   # void dealloc_xx(struct xx *)

    def rtti_node(self, defnode, node):
        node.typename = 'void (@)(void *)'
        node.implementationtypename = 'void (@)(struct %s *)' % (
            defnode.name,)
        node.name = defnode.gcinfo.static_deallocator
        node.ptrname = '((void (*)(void *)) %s)' % (node.name,)

    # zero malloc impl

    def zero_malloc(self, TYPE, esize, eresult, err):
        yield  'OP_ZERO_MALLOC(%s, %s, %s);' % (esize,
                                                eresult,
                                                err)


