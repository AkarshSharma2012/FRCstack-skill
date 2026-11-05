@echo off
rem OLLIE live physics sim (MuJoCo). Double-click to run.
rem Keys (click the 3D view first): 1 walk  2 skate  3 crawl  A auto-tour  R restart  P pause  F follow cam
rem                                UP/DOWN skate speed.  Mouse: drag orbit, right-drag pan, scroll zoom.
rem Shove OLLIE: double-click a part, then Ctrl + right-drag.
title OLLIE live physics sim
cd /d "C:\Users\Neeraj Sharma\Documents\Codex\2026-10-26\autopilot-c-users-neeraj-sharma-agents\FRCstack-skill\skills\frcstack\scripts"
echo Opening OLLIE live sim... (first launch plans the walk, about 30 s)
echo Keys: 1 walk  2 skate  3 crawl  A auto-tour  R restart  P pause  F follow  UP/DOWN skate speed
"..\..\..\.venv-sim\Scripts\python.exe" live_ollie.py --tour %*
if errorlevel 1 pause
