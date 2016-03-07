
#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import readline
import sys
import os
import shutil
import re
import subprocess
import tempfile
import termios
import fcntl

_SWIFT_RELEASES = {
	"fc261045a5": { "name": "DEV-02-25", "works": True },
	"3.0-dev": { "name": "DEV_3.0-UNKNOWN", "works": None },
	"2.2-dev": { "name": "DEV_2.2", "works": False }
}

BINARY_NAME = "swift-express"

def run_command(name, params=[], cwd=None, shell=False):
  if shell:
    subprocess.check_call(name, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd, shell=shell)
  else:
    run_params = [name]
    run_params.extend(params)
    subprocess.check_call(run_params, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd, shell=shell)

def ask_bool_question(question):
	sys.stdout.write(question)
	sys.stdout.write(" [y/n]: ")

	fd = sys.stdin.fileno()
	oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
	fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

	while True:
		try:
			response = unicode(sys.stdin.read(1)).lower()
			if response == "y" or response == "n":
				break
		except IOError: pass

	fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
	return response == "y"

def read_path():
	return raw_input("--> ").strip()

def get_swift_release(swift_bin_path):
	result = subprocess.check_output([swift_bin_path, "-version"])
	m = re.search("swift\s+([a-z0-9]+)\)", result, re.I)
	if m is not None:
		release = _SWIFT_RELEASES.get(m.group(1))
		if release is not None:
			print "Swift release is:", release["name"]
			return release
		m = re.search("version\s+([0-9a-z\.\-]+)", result, re.I)
		if m is not None:
			release = _SWIFT_RELEASES.get(m.group(1))
			if release is not None:
				print "Swift release is: ", release["name"]
			else:
				print "Can't detect Swift release"
			return release
	print "Can't detect Swift release"
	return None

def get_swift_path():
	try:
		path = subprocess.check_output(["which", "swift"]).strip("\n")
		print "Found Swift binary in:", path
		return path
	except:
		if ask_bool_question("Swift not found in your PATH. Do you want to specify Swift binary path?"):
			return read_path()
		else:
			raise KeyboardInterrupt()

def get_swift(swpath=None):
	if swpath is None:
		swpath = get_swift_path()

	try:
		release = get_swift_release(swpath)
	except:
		if ask_bool_question("Can't get release from Swift. Do you want to specify path to another Swift binary?"):
			return get_swift(read_path())
		else:
			raise KeyboardInterrupt()

	if release is None:
		print "Unkwnown Swift version. Update this script or Swift"
		raise KeyboardInterrupt()
	if release["works"] is None:
		if not ask_bool_question("Unkwnown dev release of Swift found. Proceed anyway?"):
			raise KeyboardInterrupt()
	else:
		if not release["works"]:
			if ask_bool_question("Swift Express can't be compiled with found verson of Swift. "
				"Do you want provide a path to another version?"):
				return get_swift(read_path())
	return os.path.abspath(swpath)

def get_ubuntu_release():
	with open("/etc/lsb-release") as rf:
		data = rf.read()
		vm = re.search("^DISTRIB_RELEASE=([0-9\.]+)$", data, re.M)
		if vm is None:
			print "Can't detect Ubuntu release"
			raise KeyboardInterrupt()
		return float(vm.group(1))

def install_packages():
	print "Installing Ubuntu packages by apt-get. You must provide your sudo password"
	ur = get_ubuntu_release()
	if ur < 15:
		run_command("sudo add-apt-repository --yes ppa:swiftexpress/swiftexpress", shell=True)
	run_command("sudo apt-get update && sudo apt-get install --yes "
		"clang binutils libicu-dev libevhtp-dev libevent-dev libssl-dev git", shell=True)

def download_swift_express():
	print "Downloading sources..."
	tmpdir = tempfile.mkdtemp()
	version = ""
	try:
		run_command("git clone https://github.com/crossroadlabs/ExpressCommandLine.git "+tmpdir, shell=True)
		tags = subprocess.check_output("git tag", cwd=tmpdir, shell=True).strip("\n").splitlines()
		version = tags[-1]
		run_command("git checkout "+version, cwd=tmpdir, shell=True)
	except:
		shutil.rmtree(tmpdir, ignore_errors = True)
		print "Can't download Swift Express Commandline"
		raise KeyboardInterrupt()
	return tmpdir, version

def build_swift_express(swift, folder):
	swbuild = os.path.join(os.path.dirname(swift), "swift-build")
	print "Downloading dependencies..."
	run_command(swbuild, ["--fetch"], cwd=folder)
	run_command("rm -rf Packages/*/Tests", cwd=folder, shell=True)
	print "Building..."
	run_command(swbuild, ["-c", "release"], cwd=folder)

def install_swift_express(swift, folder):
	print "Installing..."
	swpath = os.path.dirname(swift)
	if os.path.isfile(os.path.join(swpath, BINARY_NAME)):
		os.remove(os.path.join(swpath, BINARY_NAME))
	shutil.copy2(os.path.join(folder, ".build/release/"+BINARY_NAME), swpath)

def check_se_version(swift, version):
	sepath = None
	try:
		sepath = subprocess.check_output("which "+BINARY_NAME, shell=True).strip("\n")
	except: pass
	swbinsepath = os.path.join(os.path.dirname(swift), BINARY_NAME)
	if sepath is not None and swbinsepath != sepath:
		print "WARNING: Found "+BINARY_NAME+" installed not in current Swift bin folder"
	if os.path.isfile(swbinsepath):
		sepath = swbinsepath
	else:
		sepath = None
	v = "0.0.0"
	if sepath is not None:
		v = subprocess.check_output([swbinsepath, "version"]).rstrip(" \n")
		v = v[v.rfind(" "):].strip()
	if v == version:
		return ask_bool_question("Latest version already installed. Do you want to reinstall?")
	if v > version:
		print "ERROR: Version newest than latest already installed."
	return v < version

def main(noapt):
	swift = get_swift()
	dr, version = download_swift_express()
	try:
		if check_se_version(swift, version):
			if not noapt:
				install_packages()
			build_swift_express(swift, dr)
			install_swift_express(swift, dr)
			print "Swift Express Commandline installed"
	finally:
		shutil.rmtree(dr, ignore_errors = True)

def setup_readline():
	import glob
	def complete(text, state):
		return (glob.glob(os.path.expanduser(text)+'*')+[None])[state]
	readline.set_completer_delims(' \t\n;')
	readline.parse_and_bind("tab: complete")
	readline.set_completer(complete)

if __name__ == "__main__":
	setup_readline()
	noapt = False
	for arg in sys.argv:
		if arg == "--no-apt":
			noapt = True
	try:
		main(noapt)
	except KeyboardInterrupt:
		print "Installation failed"
