# To create a build of the program

## Prepare

1) Stop running the program
2) Move all files away from onedrive
3) Clear the `dist` and `build` folders and remove `main.spec`
4) Make sure `temp_data` is empty
5) Clear `data` folder
6) **IN THE BUILD DIRECTORY, NOT THE TESTING DIRECTORY:** remove the databases
7) Remove `.gitignore`, `.dockerignore` and `Dockerfile`
8) Remove `.vscode` and `__pycache__`
9) Remove folder `testing`

## Build

1) Run the command `pyinstaller --onedir main.py --add-data "cogs;cogs"`
2) Create a file called `start.bat` and put it next to the `.exe`
3) Put this in it
  ```batch
  @echo off
  title MyApp
  cd /d %~dp0

  echo Starting MyApp...
  main.exe
  
  echo.
  echo Program closed. Press any key to exit.
  pause >nul
  ```
4) Make a `.zip` file of the folder

## Finalising

### To host the bot

1) Send it over to the host
2) Tell them to unzip it
3) Tell them to find the `persistent_data` folder and move the old databases over
4) In the top-level directory they should also move over the old `.env` file
5) Let them to run `start.bat`

### To use the bot

1) In discord navigate to `Integrations` within the server settings
2) Navigate to the bot's name
3) Set commands to the specific high rank roles to use
   - Recommended roles:
     - All setup commands: owner (+ developer)
     - All reward commands: highest rank actually able to reward them (+ developer)
     - For others: own discretion (+ developer)
     Why developer? It makes it easier to debug some stuff, it isn't needed though