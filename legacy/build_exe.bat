@echo off
REM Build the Bois & Techniques Memoire Generator as a single .exe with assets
pyinstaller --noconsole --onefile --icon=assets/logo.png --add-data "assets;assets" main_gui.py
pause
