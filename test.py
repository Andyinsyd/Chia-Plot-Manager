# import requests

# headers={'Content-type':'application/json', 'Accept':'application/json'}
# url = "http://192.168.0.173:5000/api/Plot/Create"

# plot = {
#     'jobName': 'sas1',
#     'kSize': 32,
#     'totalSeconds': 255,
#     'phase1Seconds': 48,
#     'phase2Seconds': 44,
#     'phase3Seconds': 438,
#     'phase4Seconds': 428,
#     'copySeconds': 48,
#     'machine': '7700'
#     }

# x = requests.post(url, json=plot, headers = headers)

# print(x.text)
import re

str = 'Could not copy "/mnt/hdd1/plot-k32-2021-06-05-17-15-8f7b235a5be38836b61db8987c99a30899ed27d5b398b29e347fc8eb3112aae5.plot.2.tmp" to "/mnt/hub1/usb1/plot-k32-2021-06-05-17-15-8f7b235a5be38836b61db8987c99a30899ed27d5b398b29e347fc8eb3112aae5.plot.2.tmp". Error No space left on device. Retrying in five minutes.'
match = re.search(rf'Retrying in five minutes', str, flags=re.I)
if(match):
    print(match)
