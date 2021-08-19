# torobert - a babbling trophy on the wall

Torobert is a system that turns stuffed animals into chatty companions, providing you with news, entertainment and general smartassery.

Torobert is the result of a hobby project. It is not a complete application that runs out of the box on your system. It is also unsupported.

## what Torobert has to say (and when)
Torobert's texts have two major sources:
1. they are provided as static json- or Excel-files
1. they are dynamically read from websites or mails

An extendable collection of text generator modules define, what torobert has to say.

### text generators
- **general babbling**  
  The texts from this generator may contain
  - greetings for the owner, depending on the time of day and the duration of the absence
  - reminders for dates (e.g. birthdays)
  - random thoughts
- **key finder**  
  You cannot find your keys? Torobert provides some "constructive" suggestions where to look.
- **weather forecasts**  
  Torobert reads a weather forecast to you (which it fetches from your favorite weather website).
- **news**  
  Occasionaly torobert provides you with summaries of news articles taken from you favorite news sites.
- **horoscope**  
  Torobert creates a daily horoscope for you.
- **magic 8 ball**  
  You have an unanswered yes/no question? Let torobert decide for you.
- **mails**  
  Torobert reads your mails so you don't have to.
- **conversation starters**  
  Torobert provides you with challenging topics to (re)start a stalling conversation.
- **smartassery** (wiki)  
  Torobert likes to delight you with uninvited bits of only partially useful facts - taken directly from none but the most excellent Wikipedia articles.

### how texts are triggered
The text generators can be triggered by
1. a recurring timer (configurable of course, only triggered when motion is detected in the room)
1. by a smartphone, a tablet or a computer via a web application running in the local network

## hardware setup
- a hollowed out stuffed animal (e.g. a "trophy" animal to be mounted on the wall above the chimney)
- a Raspberry Pi 3 B+
- a passive infrared motion sensor (PIR) connected with a ESP8266 microchip, which establishes a serial connection to the Raspberry Pi via USB
- a set of small USB powered speakers
- a small USB hub (input connected to the power supply, outputs connected to the speakers and the power input of the Raspberry Pi)

## software setup
- operation system: Raspberry Pi OS in headless mode
- three major python programs run continuously for the user "pi" (e.g. started by cronjobs):
  - torobert.py (calls the text generators for message creation and also evokes the webApp in a seperate thread)
  - sensors.py (tells torobert.py when motion is detected so torobert knows when to talk and when to shut up)
  - talk.py (receives messages from torobert.py, converts text into audio files using Amazon Polly and then plays the audio using pygame)
- Redis remote dictionary server is used to keep states. It also manages the communication between torobert.py, sensors.py and talk.py by acting as a publish/subscribe message broker.

The files from the git repository mostly go to `/opt/torobert/torobert`.
The files from the exampleConfiguration go to `/etc/torobert` - they contain configuration files as well as the static texts.

The additional module "wifiConfig.py" can be called with root privileges when no internet connection is available. It can headlessly establish a new wifi connection when a USB drive with an ssid and a password are provided.

## detailed requirements
- necessary software packages
  - redis
  - libSDL2-2.0-0
  - libsdl2-mixer-2.0-0
- recommended software packages
  - vorbis-tools (to easily test the ogg files created by Amazon Polly)
  - git
  - python3-pip
- necessary python packages for the user "pi"
  - shell_command
  - pygame
  - redis
  - openpyxl
  - flask
  - pyserial
  - boto3
  - imapclient
  - html2text
  - bs4
- necessary python packages for the user "root"
  - shell_command
  - pygame
  - redis
