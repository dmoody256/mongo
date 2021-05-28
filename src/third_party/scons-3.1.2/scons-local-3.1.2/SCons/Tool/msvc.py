"""engine.SCons.Tool.msvc

Tool-specific initialization for Microsoft Visual C/C++.

There normally shouldn't be any need to import this module directly.
It will usually be imported through the generic SCons.Tool.Tool()
selection method.

"""

#
# Copyright (c) 2001 - 2019 The SCons Foundation
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

__revision__ = "src/engine/SCons/Tool/msvc.py bee7caf9defd6e108fc2998a2520ddb36a967691 2019-12-17 02:07:09 bdeegan"

import os.path
import os
import re
import sys

import SCons.Action
import SCons.Builder
import SCons.Errors
import SCons.Platform.win32
import SCons.Tool
import SCons.Tool.msvs
import SCons.Util
import SCons.Warnings
import SCons.Scanner.RC

from .MSCommon import msvc_exists, msvc_setup_env_once, msvc_version_to_maj_min

CSuffixes = ['.c', '.C']
CXXSuffixes = ['.cc', '.cpp', '.cxx', '.c++', '.C++']

# Logic to build .rc files into .res files (resource files)
res_scanner = SCons.Scanner.RC.RCScan()
res_action  = SCons.Action.Action('$RCCOM', '$RCCOMSTR')
res_builder = SCons.Builder.Builder(action=res_action,
                                    src_suffix='.rc',
                                    suffix='.res',
                                    src_builder=[],
                                    source_scanner=res_scanner)

def msvc_batch_key(action, env, target, source):
    """
    Returns a key to identify unique batches of sources for compilation.

    If batching is enabled (via the $MSVC_BATCH setting), then all
    target+source pairs that use the same action, defined by the same
    environment, and have the same target and source directories, will
    be batched.

    Returning None specifies that the specified target+source should not
    be batched with other compilations.
    """

    # Fixing MSVC_BATCH mode. Previous if did not work when MSVC_BATCH
    # was set to False. This new version should work better.
    # Note we need to do the env.subst so $MSVC_BATCH can be a reference to
    # another construction variable, which is why we test for False and 0
    # as strings.
    if 'MSVC_BATCH' not in env or env.subst('$MSVC_BATCH') in ('0', 'False', '', None):
        # We're not using batching; return no key.
        return None
    t = target[0]
    s = source[0]
    if os.path.splitext(t.name)[0] != os.path.splitext(s.name)[0]:
        # The base names are different, so this *must* be compiled
        # separately; return no key.
        return None
    return (id(action), id(env), t.dir, s.dir)

def msvc_output_flag(target, source, env, for_signature):
    """
    Returns the correct /Fo flag for batching.

    If batching is disabled or there's only one source file, then we
    return an /Fo string that specifies the target explicitly.  Otherwise,
    we return an /Fo string that just specifies the first target's
    directory (where the Visual C/C++ compiler will put the .obj files).
    """

    # Fixing MSVC_BATCH mode. Previous if did not work when MSVC_BATCH
    # was set to False. This new version should work better. Removed
    # len(source)==1 as batch mode can compile only one file
    # (and it also fixed problem with compiling only one changed file
    # with batch mode enabled)
    if 'MSVC_BATCH' not in env or env.subst('$MSVC_BATCH') in ('0', 'False', '', None):
        return '/Fo$TARGET'
    else:
        # The Visual C/C++ compiler requires a \ at the end of the /Fo
        # option to indicate an output directory.  We use os.sep here so
        # that the test(s) for this can be run on non-Windows systems
        # without having a hard-coded backslash mess up command-line
        # argument parsing.
        # Adding double os.sep's as if the TARGET.dir has a space or otherwise
        # needs to be quoted they are needed per MSVC's odd behavior
        # See: https://github.com/SCons/scons/issues/3106
        return '/Fo${TARGET.dir}' + os.sep*2

CAction = SCons.Action.Action("$CCCOM", "$CCCOMSTR",
                              batch_key=msvc_batch_key,
                              targets='$CHANGED_TARGETS')
ShCAction = SCons.Action.Action("$SHCCCOM", "$SHCCCOMSTR",
                                batch_key=msvc_batch_key,
                                targets='$CHANGED_TARGETS')
CXXAction = SCons.Action.Action("$CXXCOM", "$CXXCOMSTR",
                                batch_key=msvc_batch_key,
                                targets='$CHANGED_TARGETS')
ShCXXAction = SCons.Action.Action("$SHCXXCOM", "$SHCXXCOMSTR",
                                  batch_key=msvc_batch_key,
                                  targets='$CHANGED_TARGETS')

def generate(env):
    """Add Builders and construction variables for MSVC++ to an Environment."""
    static_obj, shared_obj = SCons.Tool.createObjBuilders(env)

    # TODO(batch):  shouldn't reach in to cmdgen this way; necessary
    # for now to bypass the checks in Builder.DictCmdGenerator.__call__()
    # and allow .cc and .cpp to be compiled in the same command line.
    static_obj.cmdgen.source_ext_match = False
    shared_obj.cmdgen.source_ext_match = False

    for suffix in CSuffixes:
        static_obj.add_action(suffix, CAction)
        shared_obj.add_action(suffix, ShCAction)
        static_obj.add_emitter(suffix, SCons.Defaults.StaticObjectEmitter)
        shared_obj.add_emitter(suffix, SCons.Defaults.SharedObjectEmitter)

    for suffix in CXXSuffixes:
        static_obj.add_action(suffix, CXXAction)
        shared_obj.add_action(suffix, ShCXXAction)
        static_obj.add_emitter(suffix, SCons.Defaults.StaticObjectEmitter)
        shared_obj.add_emitter(suffix, SCons.Defaults.SharedObjectEmitter)

    env['CCPDBFLAGS'] = SCons.Util.CLVar(['${(PDB and "/Z7") or ""}'])
    env['_MSVC_OUTPUT_FLAG'] = msvc_output_flag
    env['_CCCOMCOM']  = '$CPPFLAGS $_CPPDEFFLAGS $_CPPINCFLAGS $CCPDBFLAGS'
    env['CC']         = 'cl'
    env['CCFLAGS']    = SCons.Util.CLVar('/nologo')
    env['CFLAGS']     = SCons.Util.CLVar('')
    env['CCCOM']      = '${TEMPFILE("$CC $_MSVC_OUTPUT_FLAG /c $CHANGED_SOURCES $CFLAGS $CCFLAGS $_CCCOMCOM","$CCCOMSTR")}'
    env['SHCC']       = '$CC'
    env['SHCCFLAGS']  = SCons.Util.CLVar('$CCFLAGS')
    env['SHCFLAGS']   = SCons.Util.CLVar('$CFLAGS')
    env['SHCCCOM']    = '${TEMPFILE("$SHCC $_MSVC_OUTPUT_FLAG /c $CHANGED_SOURCES $SHCFLAGS $SHCCFLAGS $_CCCOMCOM","$SHCCCOMSTR")}'
    env['CXX']        = '$CC'
    env['CXXFLAGS']   = SCons.Util.CLVar('$( /TP $)')
    env['CXXCOM']     = '${TEMPFILE("$CXX $_MSVC_OUTPUT_FLAG /c $CHANGED_SOURCES $CXXFLAGS $CCFLAGS $_CCCOMCOM","$CXXCOMSTR")}'
    env['SHCXX']      = '$CXX'
    env['SHCXXFLAGS'] = SCons.Util.CLVar('$CXXFLAGS')
    env['SHCXXCOM']   = '${TEMPFILE("$SHCXX $_MSVC_OUTPUT_FLAG /c $CHANGED_SOURCES $SHCXXFLAGS $SHCCFLAGS $_CCCOMCOM","$SHCXXCOMSTR")}'
    env['CPPDEFPREFIX']  = '/D'
    env['CPPDEFSUFFIX']  = ''
    env['INCPREFIX']  = '/I'
    env['INCSUFFIX']  = ''
#    env.Append(OBJEMITTER = [static_object_emitter])
#    env.Append(SHOBJEMITTER = [shared_object_emitter])
    env['STATIC_AND_SHARED_OBJECTS_ARE_THE_SAME'] = 1

    env['RC'] = 'rc'
    env['RCFLAGS'] = SCons.Util.CLVar('/nologo')
    env['RCSUFFIXES']=['.rc','.rc2']
    env['RCCOM'] = '$RC $_CPPDEFFLAGS $_CPPINCFLAGS $RCFLAGS /fo$TARGET $SOURCES'
    env['BUILDERS']['RES'] = res_builder
    env['OBJPREFIX']      = ''
    env['OBJSUFFIX']      = '.obj'
    env['SHOBJPREFIX']    = '$OBJPREFIX'
    env['SHOBJSUFFIX']    = '$OBJSUFFIX'

    # MSVC probably wont support unistd.h so default
    # without it for lex generation
    env["LEXUNISTD"] = SCons.Util.CLVar("--nounistd")

    # Set-up ms tools paths
    msvc_setup_env_once(env)

    env['CFILESUFFIX'] = '.c'
    env['CXXFILESUFFIX'] = '.cc'


    # Issue #3350
    # Change tempfile argument joining character from a space to a newline
    # mslink will fail if any single line is too long, but is fine with many lines
    # in a tempfile
    env['TEMPFILEARGJOIN'] = os.linesep

    if 'ENV' not in env:
        env['ENV'] = {}
    if 'SystemRoot' not in env['ENV']:    # required for dlls in the winsxs folders
        env['ENV']['SystemRoot'] = SCons.Platform.win32.get_system_root()

def exists(env):
    return msvc_exists(env)

# Local Variables:
# tab-width:4
# indent-tabs-mode:nil
# End:
# vim: set expandtab tabstop=4 shiftwidth=4:
