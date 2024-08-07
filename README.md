# Pitop
![Build Status](https://github.com/ymode/pitop/actions/workflows/python-app.yml/badge.svg) ![GitHub commit activity](https://img.shields.io/github/commit-activity/w/ymode/pitop) ![GitHub issues](https://img.shields.io/github/issues/ymode/pitop) ![Codacy grade](https://img.shields.io/codacy/grade/bb24b7cc66374668848cc02d4a3a5396)

A small (and _somewhat OS agnostic_) user configurable python based TUI for terminal.

![image](https://github.com/ymode/pitop/assets/5312047/75b5e0b2-8e92-4a6b-afa8-c9d8c322f1dd)




# Features
+  ✅ Compatible with tmux and other terminal multiplexers, will dynamically resize to fit most tmux applications
+  🛜 Webserver mode, start Pitop with --web flag and pitop will serve on http://localhost:5000/
+  💀 Highlight and kill unwanted processes
+  📈 Monitor CPU/RAM/Battery/Network
+  🐍 Written in python to encourage people to hack/modify it to suit their own needs
+  🎨 Now with user defined color palette support! 
  
Works great in [tmux](https://github.com/tmux/tmux)

![image](https://github.com/ymode/pitop/assets/5312047/ce2b7d40-18cf-4d88-ae89-adbaa094ccff)




# Install

```
git clone https://github.com/ymode/pitop.git

cd pitop

pip install .

cd pittop 

pitop

```
Or if you prefer [pre-release-source](https://github.com/ymode/pitop/releases/tag/v0.3-alpha)
# Help
Pitop [Wiki](https://github.com/ymode/pitop/wiki)

Pitop targets Python 3.11.x however it supports 3.10.x and higher.

In some cases (depending on the OS/distro) the system may not recognise the entry point in setup.py and will not allow the program to be run from the  ``` pitop ``` command.

If this happens you can choose to force pitop to be an executable with the following 

```
cd pitop/pitop
chmod +x pitop.py
pitop

```

Alternatively if you just want to run pitop as a python script

```
cd pitop/pitop
./pitop.py

```
Also see: [known issues](https://github.com/ymode/pitop/issues)

# Future
Pitop remains in active development with a focus on v0.4a-pre-release as the next target. This version will bring better macOS support and feature/widget customisation.

# Contribute
Looking for a place to start contributing or have a feature request? see: [issues](https://github.com/ymode/pitop/issues) 





