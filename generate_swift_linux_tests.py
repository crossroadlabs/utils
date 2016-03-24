#!/usr/bin/env python
from os import path
import os
import glob
import sys
import re

_test_class_re = re.compile("class\s+(\w+)\s*:\s*XCTestCase\s*\{")
_test_func_re = re.compile("func\s+(test\w+)\s*\(\s*\)")

def get_test_files(in_path):
    output = []
    for root, dirs, files in os.walk(in_path):
        for file in files:
            if file.endswith("swift") and not file.endswith("LinuxMain.swift"):
                output.append(path.join(root, file))
    return output

def get_test_classes(in_string):
    return _test_class_re.findall(in_string)

def get_end_index(in_string, class_start_index, open = "{", close = "}", or_close = None):
    count = 0
    length = len(in_string)
    index = class_start_index
    if or_close is None:
      or_close = close
    max_length = max(len(open), len(close), len(or_close))
    while index < length:
        char = in_string[index:index+max_length+1]
        if char.startswith(open):
            count += 1
        elif char.startswith(close) and close != or_close:
            count -= 1
        elif char.startswith(or_close):
            count -= 1
            if count <= 0:
                return index+len(or_close)
        index += 1
    return index

def get_class_substring(in_string, class_start_index):
    return in_string[class_start_index:get_end_index(in_string, class_start_index)]

def get_test_method_list(class_string):
    return _test_func_re.findall(class_string)

def get_test_methods(in_string, for_class):
    methods = []
    class_re = "class\s+"+ for_class + "\s*:\s*XCTestCase\s*\{"
    match = re.search(class_re, in_string)
    methods.extend(get_test_method_list(get_class_substring(in_string, match.start())))
    ext_re = re.compile("extension\s+"+for_class+"\s*\{")
    for match in ext_re.finditer(in_string):
        methods.extend(get_test_method_list(get_class_substring(in_string, match.start())))
    return methods

def remove_linux_allMethods(in_string, for_class):
    if_re = re.compile("#if\s+os\s*\(\s*Linux\s*\)\s+")
    allm_re = re.compile("extension\s+"+ for_class + "\s*\{\s*static\s+var\s+allTests")
    match = if_re.search(in_string)
    while match is not None:
        index = match.end()
        end_pos = get_end_index(in_string, match.start()-1, "#if", "#endif")
        res = in_string[match.start():end_pos]
        if allm_re.search(res) is not None:
            in_string = in_string[:match.start()] + in_string[end_pos:]
            index = match.start()
        match = if_re.search(in_string, index)
    return in_string.rstrip(" \n\t\r")

def add_linux_allMethods(in_string, classes):
    res = "\n\n#if os(Linux)\n"
    for cls, methods in classes.iteritems():
        res += "extension "+cls+" {\n" \
            "\tstatic var allTests : [(String, "+cls+" -> () throws -> Void)] {\n" \
            "\t\treturn [\n"
        for method in methods:
            res += "\t\t\t(\""+method+"\", "+method+"),\n"
        res += "\t\t]\n\t}\n}\n#endif"
    return in_string+res

def cleanup_ifdefs(in_string):
  if_re = re.compile("#if\s+(.+?)\n")
  Linux = True
  OSX = FreeBSD = iOS = tvOS = watchOS = False
  arm = arm64 = i386 = False
  x86_64 = True
  dispatch = False
  arch = os = lambda o: o
  DEBUG = False

  match = if_re.search(in_string)

  while match is not None:
    index = match.end()
    result = eval(match.group(1).replace("!", "not ").replace("||", "or").replace("&&", "and"))
    pos_endif = get_end_index(in_string, match.start()-1, "#if", "#endif")
    pos_else = get_end_index(in_string, match.start()-1, "#if", "#endif", "#else")
    if result:
      if pos_else < pos_endif:
        in_string = in_string[:pos_else-len("#else")] + "#endif\n" + in_string[pos_endif:]
        index = pos_else
    else:
      if pos_else < pos_endif:
        in_string = in_string[:match.start()] + "#if True\n" + in_string[pos_else:]
        index = match.start()
      else:
        in_string = in_string[:match.start()] + in_string[pos_endif:]
        index = match.start()
    match = if_re.search(in_string, index)
  return in_string


def process_test_file(file_path):
    res = open(file_path, "rt").read().decode("utf8")
    cleaned = cleanup_ifdefs(res)
    classes = {}
    class_list = get_test_classes(cleaned)
    for cls in class_list:
        classes[cls] = get_test_methods(cleaned, cls)
        res = remove_linux_allMethods(res, cls)
    res = add_linux_allMethods(res, classes)
    open(file_path, "wt").write(res.encode("utf8"))
    return (path.basename(path.dirname(file_path)), path.basename(file_path), class_list)


def process_linux_main(proj_path, files_info):
    res = "import XCTest\n\n"
    for pkg in files_info.keys():
        res += "@testable import "+pkg+"TestSuite\n"
    res += "\nXCTMain([\n"
    for pkg in files_info.values():
        for file, info in pkg:
            for cls in info:
                res += "\ttestCase("+cls+".allTests),\n"
    res += "])"
    open(path.join(path.join(proj_path, "Tests"), "LinuxMain.swift"), "wt").write(res)


if __name__ == "__main__":

    files = get_test_files(path.join(sys.argv[1], "Tests"))
    test_names = map(lambda file: process_test_file(file), files)

    def red_func(d, v):
        if d.get(v[0]) is None:
            d[v[0]] = []
        d[v[0]].append((v[1], v[2]))
        return d

    test_names = reduce(red_func, test_names, {})
    process_linux_main(sys.argv[1], test_names)
    print "OK"
