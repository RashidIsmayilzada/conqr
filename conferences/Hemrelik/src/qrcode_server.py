#!/usr/bin/env python3
###############################################################################
#
#  ConQR Web Server. Should work on any OS with Python
#
#  Written by: Dave Kennedy (ReL1K)
#  Website: https://www.trustedsec.com
#
################################################################################

import sys
import socket
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import threading

from src.core import check_in, extract_qr_code, guests_csv_path, render_home_page

# main dns class
class DNSQuery:
  def __init__(self, data):
    self.data = data
    self.dominio = ''

    tipo = (data[2] >> 3) & 15   # Opcode bits
    if tipo == 0:                     # Standard query
      ini = 12
      lon = data[ini]
      while lon != 0:
        self.dominio += data[ini+1:ini+lon+1].decode("utf-8", "replace") + '.'
        ini += lon + 1
        lon = data[ini]

  def respuesta(self, ip):
    packet = b''
    if self.dominio:
      packet += self.data[:2] + b"\x81\x80"
      packet += self.data[4:6] + self.data[4:6] + b'\x00\x00\x00\x00'   # Questions and Answers Counts
      packet += self.data[12:]                                         # Original Domain Name Question
      packet += b'\xc0\x0c'                                             # Pointer to domain name
      packet += b'\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'             # Response type, ttl and resource data length -> 4 bytes
      packet += bytes(int(x) for x in ip.split('.')) # 4bytes of IP
    return packet

def _looks_like_ip(value):
	parts = value.split(".")
	if len(parts) != 4:
		return False
	try:
		return all(0 <= int(part) <= 255 for part in parts)
	except ValueError:
		return False

# grab the ipaddress from argv, env, or prompt
if os.environ.get("CONQR_IP"):
	ipaddr = os.environ["CONQR_IP"]
elif len(sys.argv) > 1 and _looks_like_ip(sys.argv[-1]):
	ipaddr = sys.argv[-1]
else:
	ipaddr = input("Enter the IP address to point machines to the QR Code Web Server: ")

# main dns routine
def dns(ipaddr):
  print("[*] Started DNS Server for ConQR..")
  print("[*] You NEED to configure your wireless AP or network to give DNS to THIS server")
  print("[*] This server will redirect all DNS requests when the QRCode is scanned to the server!")
  udps = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    udps.bind(('', 53))
  except OSError as error:
    print("[!] Could not bind DNS on port 53 (%s). Continuing without DNS." % (error))
    return

  try:
    while 1:
      data, addr = udps.recvfrom(1024)
      p = DNSQuery(data)
      udps.sendto(p.respuesta(ipaddr), addr)
      print('Response: %s -> %s' % (p.dominio, ipaddr))
  except KeyboardInterrupt:
    print("Exiting the DNS Server..")
    udps.close()

# start dns in a background thread so macOS spawn does not re-import this module
dns_thread = threading.Thread(target=dns, args=(ipaddr,), daemon=True)
dns_thread.start()


class HTTPHandler(SimpleHTTPRequestHandler):

	def do_GET(self):
		parsed_path = urlparse(self.path)
		path = parsed_path.path

		if path == "/qrcode":
			code = extract_qr_code(parsed_path.query)
			result = check_in(code, guests_csv_path())
			body = result["html"].encode("utf-8")
			self.send_response(200)
			self.send_header("Content-type", "text/html; charset=utf-8")
			self.send_header("Content-Length", str(len(body)))
			self.end_headers()
			self.wfile.write(body)
			return

		if path == "/":
			body = render_home_page().encode("utf-8")
			self.send_response(200)
			self.send_header("Content-type", "text/html; charset=utf-8")
			self.send_header("Content-Length", str(len(body)))
			self.end_headers()
			self.wfile.write(body)
			return

		SimpleHTTPRequestHandler.do_GET(self)

def main(server_class=HTTPServer, handler_class=HTTPHandler):
	try:
		port = int(os.environ.get("CONQR_PORT", "80"))
		try:
			server_address = ('', port)
			httpd = server_class(server_address, handler_class)
		except OSError as error:
			if port == 80:
				print("[!] Could not bind port 80 (%s). Falling back to 8080." % (error))
				port = 8080
				server_address = ('', port)
				httpd = server_class(server_address, handler_class)
			else:
				raise
		print("{*} The ConQR Server is running on port %s, open a local browser or remote to view... {*}" % (port))
		httpd.serve_forever()

	except KeyboardInterrupt:
		print("[!] Exiting the web server...\n")
	except Exception as error:
		print("[!] Something went wrong, printing error: " + str(error))
		sys.exit()

main()
