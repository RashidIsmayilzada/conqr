#!/usr/bin/env python3
#####################################################
#
# con generation tool
#
#
# This tool is used to generate a conference
#
#####################################################
import csv
import shutil
import getpass
import time
import os

GUEST_FIELDNAMES = [
	"qr_code",
	"buyer_email",
	"full_name",
	"payment",
	"table",
	"baby_kid",
	"emailed",
	"checked_in",
	"checked_in_at",
]

# make the directory if not there
if not os.path.isdir("conferences/"):
	os.mkdir("conferences/")

# initial try/except block
try:

	# start the menu system loop
	while 1:
		
		# start the menu
		print("\nWelcome to the ConQR event setup tool. This will create a folder for your\nrestaurant event, email QR tickets, and a check-in page for staff phones.")

		print('\nFirst things first, what is the name of the event, as an example "Saturday tasting menu"')
		while 1:
			# if we dont specify a name then keep looping
			con_name = input("\n[-] Enter the name of the event: ")
			if con_name != "":
				break

		# now we need to take in what folder to store under conferences
		print("\nGreat! Thanks. Now we need to know what name to store the event as. This will\nultimately be under the conferences/ directory in the ConQR folder root.\n\nThis can only be one word, so for example saturdaydinner")
		while 1:
			conference_folder = input("\n[-] Enter the name to store under the conferences folder: ")
			if " " not in conference_folder:
				if conference_folder != "":
					break

		#
		# mail server to hook into
		#		
		print("\nNow we need to know if you are using your own mail server or gmail.\n\n1. I'm using my own mail server.\n2. I'm using Gmail\n")
		while 1:
			mail_handler = input("[-]Enter number 1 or number 2 for mail provider: ")
			if mail_handler == "1" or mail_handler == "2":
				# if we are using our own server
				if mail_handler == "1":
					mailserver = input("Enter the smtp address of the mail server: ")
					port = input("Enter the port of the mail server: ")

				# if we are using gmail for our mail server
				if mail_handler == "2":
					mailserver = "smtp.gmail.com"
					port = "587"

				break


		#
		# specify username and pwd
		#
		print("\nEnter the username to authenticate to the server, i.e. gmail pwd or your own mail server (can be an email addy)\n")
		while 1:
			username = input("Enter the username to authenticate to the mail server: ")
			if username != "":
				break

		#
		# grab the password
		# 
		print("\nNext we need the password for the account. NOTE that this is STORED in clear inside the conference folder.\n")
		while 1:
			password = getpass.getpass("Enter the password for the mail server (will not show on screen): ")
			if password != "":
				break

		#
		# conference dates
		#
		print("\nEnter the event date in whatever format you want; this goes in the ticket email (you can change it later)\n")
		while 1:
			date = input("Enter the date for the event (example September 25, 2026): ")
			if date != "":
				break

		print("\nPhones that scan a ticket must reach this laptop on restaurant Wi-Fi.\nEnter this machine's LAN IP, for example 192.168.1.20\n")
		while 1:
			qr_host = input("Enter the QR / check-in server IP: ").strip()
			if qr_host != "":
				break

		qr_port = input("Enter the check-in HTTP port [8080]: ").strip() or "8080"

		# prompt the user to start
		create_con = input("Okay. That's everything we needed. Are you ready to create the conference? [y/n]: ")
		# if no then bomb out and exit
		if create_con == "n": break
		# if yes then omg so hot
		if create_con == "" or create_con.lower() == "y" or create_con == "yes":
			print("""                                                         
  ,----..                           ,----..              
 /   /   \\                         /   /   \\             
|   :     :  ,---.        ,---,   /   .     :    __  ,-. 
.   |  ;. / '   ,'\\   ,-+-. /  | .   /   ;.  \\ ,' ,'/ /| 
.   ; /--` /   /   | ,--.'|'   |.   ;   /  ` ; '  | |' | 
;   | ;   .   ; ,. :|   |  ,"' |;   |  ; \\ ; | |  |   ,' 
|   : |   '   | |: :|   | /  | ||   :  | ; | ' '  :  /   
.   | '___'   | .; :|   | |  | |.   |  ' ' ' : |  | '    
'   ; : .'|   :    ||   | |  |/ '   ;  \\; /  | ;  : |    
'   | '/  :\\   \\  / |   | |--'   \\   \\  ',  . \\|  , ;    
|   :    /  `----'  |   |/        ;   :      ; |---'     
 \\   \\ .'           '---'          \\   \\ .'`--"          
  `---`                             `---`                """)

			print("[*] Prepping the directories needed for the conference.")
			time.sleep(1)
			# if there is a conference name like that already
			if os.path.isdir("conferences/" + conference_folder):
				choice1 = input("[-] Old conference detected, do you want to delete it [y/n]: ")
				if choice1 == "n":
					break

				if choice1 == "y":
					shutil.rmtree("conferences/" + conference_folder)
					print("[*] Okay removing the directories...")
					os.mkdir("conferences/" + conference_folder)

			else:
				os.mkdir("conferences/" + conference_folder)

			print("[*] Finished creating a new folder under conferences/" + conference_folder)
			print("[*] Creating necessary file and folder structures...")
			os.mkdir("conferences/%s/database" % (conference_folder))
			print("[*] Created database folder, this will store the guests.")
			os.mkdir("conferences/%s/configuration" % (conference_folder))
			print("[*] Creating the configuration directory, this will be used for your config.")
			os.mkdir("conferences/%s/src" % (conference_folder))
			print("[*] Created the src directory, used for housing the main application.")
			print("[*] We have all of the necessary files, now writing out everything we need.")

			# copy the appropriate files over
			shutil.copy("src/core.py", "conferences/%s/src/" % (conference_folder))
			shutil.copy("src/conqr.py", "conferences/%s/" % (conference_folder))
			shutil.copy("src/qrcode_server.py", "conferences/%s/src" % (conference_folder))
			shutil.copy("src/__init__.py", "conferences/%s/src" % (conference_folder))
			shutil.copy("src/qrcode.py", "conferences/%s/src" % (conference_folder))
			shutil.copy("src/con_noprompt.py", "conferences/%s/" % (conference_folder))
			guests_path = "conferences/%s/database/guests.csv" % (conference_folder)
			with open(guests_path, "w", newline="", encoding="utf-8") as guests_file:
				writer = csv.DictWriter(guests_file, fieldnames=GUEST_FIELDNAMES)
				writer.writeheader()
			bookings_path = "conferences/%s/bookings.csv" % (conference_folder)
			with open(bookings_path, "w", newline="", encoding="utf-8") as bookings_file:
				writer = csv.DictWriter(bookings_file, fieldnames=["buyer_email", "full_name", "payment", "table", "baby_kid"])
				writer.writeheader()
				writer.writerow({
					"buyer_email": "anna@example.com",
					"full_name": "Anna Smith",
					"payment": "paid",
					"table": "12",
					"baby_kid": "no",
				})
				writer.writerow({
					"buyer_email": "anna@example.com",
					"full_name": "Bob Smith",
					"payment": "paid",
					"table": "12",
					"baby_kid": "no",
				})
				writer.writerow({
					"buyer_email": "anna@example.com",
					"full_name": "Cara Smith",
					"payment": "pay_at_restaurant",
					"table": "12",
					"baby_kid": "yes",
				})
			print("[*] Created database/guests.csv and a sample bookings.csv (one row per guest).")
			with open("conferences/%s/configuration/config" % (conference_folder), "w") as filewrite:
				filewrite.write("""
#
# ConQR automatic configuration file. This contains all of the information
# needed in order to use the ConQR applicaton successfully
#
#
# SMTP USERNAME
SMTP_USER="%s"
# SMTP PASSWORD
SMTP_PASS="%s"
# SMTP SERVER ADDRESS
SMTP_SERVER="%s"
# PORT FOR SMTP SERVER
SMTP_PORT="%s"
# EVENT NAME
EVENT_NAME="%s"
# EVENT DATE
EVENT_DATE="%s"
# LAN IP (or host:port) phones use when they scan a ticket
QR_HOST="%s"
# HTTP port for the check-in server
QR_PORT="%s"
# TICKET EMAIL SUBJECT
TICKET_SUBJECT="Your tickets for {event}"
# TICKET EMAIL BODY. Guest names are appended automatically.
TICKET_TEMPLATE="Greetings!\\n\\nAttached are the QR tickets for {event}. Each person has their own QR code. Bring them on a phone or printed at the door.\\n\\nEvent date: %s"
# CONFERENCE FOLDER
CONFERENCE_FOLDER="%s"

			""" % (username, password, mailserver, port, con_name, date, qr_host, qr_port, date, conference_folder))
			print("[*] Finished. Edit conferences/%s/bookings.csv, then run:" % (conference_folder))
			print("    python3 conqr.py send bookings.csv")
			print("    python3 conqr.py 4")
			break

except KeyboardInterrupt:
	print("\n\n[*] Exiting the ConQR system, thanks for shopping with us.")
	print("\n[*] Visit us at https://www.trustedsec.com")

except Exception as e:
	print("Something went wrong, printing the error: " + str(e))

finally: 
	print("[*] Thanks for using the ConQR generator. Please visit https://www.trustedsec.com for more goodness.")
