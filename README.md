# Pitop
![Build Status](https://github.com/ymode/pitop/actions/workflows/python-app.yml/badge.svg) ![GitHub commit activity](https://img.shields.io/github/commit-activity/w/ymode/pitop) ![GitHub issues](https://img.shields.io/github/issues/ymode/pitop) ![Codacy grade](https://img.shields.io/codacy/grade/bb24b7cc66374668848cc02d4a3a5396)




A small (and somewhat OS agnostic) python based TUI for terminal.



<img width="1182" alt="pitop_8" src="https://github.com/ymode/pitop/assets/5312047/c6a55809-e769-4e8c-9837-2bcb2c96e9c6">

# Features
+ Compatible with tmux and other terminal multiplexers, will dynamically resize to fit most tmux applications
+ Highlight and kill unwanted processes
+ Monitor CPU/RAM/Battery/Network
+ Written in python to encourage people to hack/modify it to suit their own needs
  
Works great in [tmux](https://github.com/tmux/tmux)

<img width="1087" alt="pitop_9" src="https://github.com/ymode/pitop/assets/5312047/7a8b4219-4fe1-4bc7-b529-be2c2dec6fa9">



# Install

```
git clone https://github.com/ymode/pitop.git

cd pitop

pip install . 

pitop

```
Or if you prefer [pre-release-source](https://github.com/ymode/pitop/releases/tag/v0.1.1-alpha)
# Help

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
Pitop remains in active development with a focus on v0.2a-pre-release as the next target. This version adopts an entirely new codebase and focuses on visual upgrades as well as QoL improvements.

![image](https://github.com/ymode/pitop/assets/5312047/e4550f6e-5f0e-40d0-b738-35e2dc04c971)
_pitop-v0.2a-pre-release_


