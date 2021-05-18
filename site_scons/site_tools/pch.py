# Copyright 2021 MongoDB Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#


import SCons
import pathlib


def update_scanner(env, builder):
    """Update the scanner for "builder" to also scan library dependencies."""

    old_scanner = builder.target_scanner
    if old_scanner:
        path_function = old_scanner.path_function
    else:
        path_function = None

    def new_scanner(node, env, path=()):
        if old_scanner:
            result = old_scanner.function(node, env, path)
        else:
            result = []

        pchobjs = set()
        for lib in result:
            for child in lib.sources:
                if child.get_env().get('PCH'):
                    #pchobjs.add(child.get_env().File(removePchExt(child.get_env().get('PCH')) + env['PCHSUFFIX']))
                    pchobjs.add(child.get_env().get('PCH'))
        env['PCHINCLUDES'] = list(pchobjs)
        result += env['PCHINCLUDES']

        return result

    builder.target_scanner = SCons.Scanner.Scanner(
        function=new_scanner, path_function=path_function
    )

def validate_vars(env):
    """Validate the PCH and PCHSTOP construction variables."""
    if 'PCH' in env and env['PCH']:
        if 'PCHSTOP' not in env:
            raise SCons.Errors.UserError("The PCHSTOP construction must be defined if PCH is defined.")
        if not SCons.Util.is_String(env['PCHSTOP']):
            raise SCons.Errors.UserError("The PCHSTOP construction variable must be a string: %r"%env['PCHSTOP'])

def pch_emitter(target, source, env):
    """Adds the object file target."""

    validate_vars(env)

    pch = None
    obj = None

    for t in target:
        if SCons.Util.splitext(str(t))[1] == env['PCHSUFFIX']:
            pch = t

    target = [pch] # make compatible with window pch interface
    env.Depends(target, env['PCHCHAIN'])
    #env.Depends(removePchExt(pch) + env['OBJSUFFIX'], env['PCHCHAIN'])
    return (target, source)

def removePchExt(file):
    return SCons.Util.splitext(SCons.Util.splitext(str(file))[0])[0]

def object_emitter(target, source, env, parent_emitter):
    """Sets up the PCH dependencies for an object file."""

    validate_vars(env)

    parent_emitter(target, source, env)

    if 'PCH' in env and env['PCH']:
        #env.Depends(target, removePchExt(env['PCH']) + env['OBJSUFFIX'])
        env.Depends(target, env['PCH'])
    return (target, source)

def static_object_emitter(target, source, env):
    return object_emitter(target, source, env,
                          SCons.Defaults.StaticObjectEmitter)

def shared_object_emitter(target, source, env):
    return object_emitter(target, source, env,
                          SCons.Defaults.SharedObjectEmitter)

def pchsuffixGen(target, source, env, for_signature):
    return SCons.Util.splitext(str(source[0]))[1] + env['PCHSUFFIX']

pch_action = SCons.Action.Action('$PCHCOM', '$PCHCOMSTR')

pch_builder = SCons.Builder.Builder(action=pch_action,
                                    emitter=pch_emitter,
                                    source_scanner=SCons.Tool.SourceFileScanner)

pch_obj_action = SCons.Action.Action('$PCHOBJCOM', '$PCHOBJCOMSTR')
pch_obj_builder = SCons.Builder.Builder(action=pch_obj_action,
                                    source_suffix='PCHSUFFIX',
                                    single_source=True,
                                    suffix='$OBJSUFFIX')

CSuffixes = ['.c', '.C']
CXXSuffixes = ['.cc', '.cpp', '.cxx', '.c++', '.C++']

def pchObjsGenerator(target, source, env, for_signature):
    command_line = []
    for include in env.get('PCHINCLUDES', []):
        command_line += [include]

    return command_line or ""

def chainPchGenerator(target, source, env, for_signature):
    command_line = []
    for pch in reversed(env.get('PCHCHAIN', [])):
        command_line += ['-include-pch', pch]
        #command_line += ['-include',  SCons.Util.splitext(str(pch.srcnode()))[0]]
        break
    return command_line or ""

def includePchGenerator(target, source, env, for_signature):
    command_line = []
    for pch in reversed(env.get('PCHCHAIN', [])):
        command_line += ['-include-pch', pch]
    return command_line or ""

def generate(env, **kwargs):

    for tool in env.get('TOOLS', []):
        if env.ToolchainIs('msvc'):
            print("ERROR: cannot not use pch tool with msvc tool")
            return
        if env.ToolchainIs('clang'):
            env['PCHSUFFIX'] = '.pch'
            break
        if env.ToolchainIs('gcc'):
            env['PCHSUFFIX'] = '.gch'
            break

    if 'PCHSUFFIX' not in env:
        print("ERROR: pch tool needs gcc or clang tools loaded first")
        return



    static_obj, shared_obj = SCons.Tool.createObjBuilders(env)
    for suffix in CSuffixes:
        static_obj.add_emitter(suffix, static_object_emitter)
        shared_obj.add_emitter(suffix, shared_object_emitter)

    for suffix in CXXSuffixes:
        static_obj.add_emitter(suffix, static_object_emitter)
        shared_obj.add_emitter(suffix, shared_object_emitter)

    update_scanner(env, env['BUILDERS']['Program'])
    update_scanner(env, env['BUILDERS']['SharedLibrary'])

    #env['CCPDBFLAGS'] = SCons.Util.CLVar(['${(PDB and "/Z7") or ""}'])
    #env['CCPCHFLAGS'] = SCons.Util.CLVar(['${(PCH and "/Yu%s \\\"/Fp%s\\\""%(PCHSTOP or "",File(PCH))) or ""}'])
    env['_PCHSUFFIX'] = pchsuffixGen

    #'$CXX -o $TARGET -c $CXXFLAGS $CCFLAGS $_CCCOMCOM $SOURCES'
    #env['PCHCOM'] = '$CXX $CXXFLAGS $CCFLAGS $CPPFLAGS $_CPPDEFFLAGS $_CPPINCFLAGS $SOURCE -o $TARGET'
    env['PCHOBJCOM'] = env['CXXCOM'].replace('_CCCOMCOM', '$CPPFLAGS $_CPPDEFFLAGS -fdata-sections -ffunction-sections')
    env['PCHCOM'] = env['CXXCOM'].replace(' -c ', ' -x c++-header ') + ' $_CHAINPCH'
    env.Append(CPPFLAGS=['-Winvalid-pch', '$_INLCUDEPCH'])
    env['BUILDERS']['PCH'] = pch_builder
    env['BUILDERS']['PCHOBJ'] = pch_obj_builder
    env['_PCHINCLUDES'] = pchObjsGenerator
    env['_CHAINPCH'] = chainPchGenerator
    env['_INLCUDEPCH'] = includePchGenerator
    env['PCHCHAIN'] = []
    #env.Append(_LIBFLAGS=' $_PCHINCLUDES')


def exists(env):
    for tool in env.get('TOOLS', []):
        if 'msvc' == tool:
            return False

        if 'clang' == tool:
            return True
        if 'gcc' == tool:
            return True