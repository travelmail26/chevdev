import json

raw = r"""BEGIN_JSON
{
  "candidates_count": 35,
  "candidates": [
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 32,
      "role": "assistant",
      "temp_raw": "176\u00b0F",
      "message": "Thanks for the update. Sounds like you got the steam you were aiming for at around 176\u00b0F when you lifted the lid. Noted."
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 33,
      "role": "user",
      "temp_raw": "174c",
      "message": "[video_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/BAACAgQAAxkBAAIKWWjtLhJBizP0dWxcjyW4vUehN5hTAAJoHAACjSRxU_eMUdbfpdolNgQ.mp4]"
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 55,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgQAAxkBAAIKb2jtMzJJ5oLZek-QIlqTCrArasXfAAJ9zjEbjSRxU0aRyX8nl01XAQADAgADeQADNgQ.jpg]"
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 57,
      "role": "user",
      "temp_raw": "185\u00b0",
      "message": "This is a picture of the onions think now it's been I don't know maybe 30 minutes they're starting to get more translucent noticeable some browning and some of the smaller parts and the temperature is about 185\u00b0 on the pan"
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 58,
      "role": "assistant",
      "temp_raw": "185\u00b0F",
      "message": "Thanks for the update. Noted: about 30 minutes in, onions are more translucent with some browning on smaller pieces; pan around 185\u00b0F."
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 59,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgQAAxkBAAIKc2jtOHagbD2KGk5za-bkwr3B0Q9wAAKMzjEbjSRxU2uulTQYn-EpAQADAgADeQADNgQ.jpg]"
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 61,
      "role": "user",
      "temp_raw": "180 degrees",
      "message": "Friend onions on white background parchment. These were softened for about an hour at low temperature around 180 degrees then kicked up to around 300 degrees for about 15 minutes. Crunchy and spots of brown around edges or small pieces with larger ones translucent white. Maintains texture crunch with some browning flavor"
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 61,
      "role": "user",
      "temp_raw": "300 degrees",
      "message": "Friend onions on white background parchment. These were softened for about an hour at low temperature around 180 degrees then kicked up to around 300 degrees for about 15 minutes. Crunchy and spots of brown around edges or small pieces with larger ones translucent white. Maintains texture crunch with some browning flavor"
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 62,
      "role": "assistant",
      "temp_raw": "180\u00b0F",
      "message": "Thanks for the update. Noted: softened ~1 hour at ~180\u00b0F, then ~300\u00b0F for ~15 minutes, yielding crunchy edges, brown spots, and translucent larger pieces. Glad the texture and flavor are working for you."
    },
    {
      "date": "2025-10-13T17:37:31.473218+00:00",
      "session_id": "7815621459_13102025_161638_631026",
      "message_index": 62,
      "role": "assistant",
      "temp_raw": "300\u00b0F",
      "message": "Thanks for the update. Noted: softened ~1 hour at ~180\u00b0F, then ~300\u00b0F for ~15 minutes, yielding crunchy edges, brown spots, and translucent larger pieces. Glad the texture and flavor are working for you."
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 3,
      "role": "user",
      "temp_raw": "174c",
      "message": "[video_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/BAACAgEAAxkBAAIJ9Wjrn2ctnEAQeckHQH71gtT_l6b5AALhBAACCgpgR7dChDWe7VajNgQ.mp4]"
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 21,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgEAAxkBAAIKB2jrs9GCPq5UoKXUFE47hzOOFdsUAAI1C2sbCgpgR25TxOwQxiByAQADAgADeQADNgQ.jpg]"
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 23,
      "role": "user",
      "temp_raw": "180\u00b0",
      "message": "most of these photos, deal with me trying to caramelize some onions on the right bottom burner of the heavy bottom pan. Been cooking for about an hour maybe an hour and a half if the temperature drops below about 180\u00b0 then the caramel then the onions don\u2019t seem to caramelize very well, but it\u2019s difficult to keep the panin the 180 to 200 range"
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 24,
      "role": "assistant",
      "temp_raw": "200\u00b0F",
      "message": "Thanks for the detailed update. Holding a steady 180\u2013200\u00b0F on a burner can definitely be tricky. I\u2019m here if you want help dialing it in or analyzing anything."
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 25,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgEAAxkBAAIKC2jrtcylXOfWngrHcngIAAFxdhlgDgACNwtrGwoKYEcBMaJVOyc4iQEAAwIAA3kAAzYE.jpg]"
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 27,
      "role": "user",
      "temp_raw": "200\u00b0",
      "message": "in this photo, some parts of the pan are over 200\u00b0 some parts of the pan are around. I think it was around 184\u00b0 this you can see from the photo that some of the onions begin to get brown while others stay more translucent, pale yellow. And this matters because some of them could start to burn more quickly and I wanna keep it I want the caramelization process..."
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 27,
      "role": "user",
      "temp_raw": "184\u00b0",
      "message": "in this photo, some parts of the pan are over 200\u00b0 some parts of the pan are around. I think it was around 184\u00b0 this you can see from the photo that some of the onions begin to get brown while others stay more translucent, pale yellow. And this matters because some of them could start to burn more quickly and I wanna keep it I want the caramelization process..."
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 29,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgEAAxkBAAIKD2jr0ruAg108ROmd662ZycYVbUsBAAJJC2sbCgpgR3WOYJ9wWwt2AQADAgADeQADNgQ.jpg]"
    },
    {
      "date": "2025-10-12T16:11:11.470553+00:00",
      "session_id": "1275063227_12102025_122338_874397",
      "message_index": 31,
      "role": "user",
      "temp_raw": "145",
      "message": "The previous image shows what caramelized onions, previously caramelized onions that were previously frozen and then placed into a bag with egg yolk probably about a one to one ratio of eggs to caramelized onions. It was sous vide in a Ziploc bag at 145.5\u00b0 for about three hours. It\u2019s not quite jammy but that actually no it\u2019s kind of a thick jam. The orange i..."
    },
    {
      "date": "2025-10-10T18:19:55.509711+00:00",
      "session_id": "1275063227_10102025_181726_554112",
      "message_index": 1,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgEAAxkBAAIJ6WjpTbOY-hgoWkXxQrBtmsAw_Y36AAIeC2sb871JRyvctI9AxejkAQADAgADeQADNgQ.jpg]"
    },
    {
      "date": "2025-10-10T18:19:55.509711+00:00",
      "session_id": "1275063227_10102025_181726_554112",
      "message_index": 3,
      "role": "user",
      "temp_raw": "141",
      "message": "I tried a different experiment. I put three different bags of eggs, one a full egg in a Ziploc bag one egg with caramelized onions that have been caramelized for about two hours maybe if I recall right and that was one yolk and both of the bags with caramelized onions were put in sous vide for about more than six hours overnight. One was cooked at 141.5\u00b0 the..."
    },
    {
      "date": "2025-10-10T18:19:55.509711+00:00",
      "session_id": "1275063227_10102025_181726_554112",
      "message_index": 3,
      "role": "user",
      "temp_raw": "145",
      "message": "I tried a different experiment. I put three different bags of eggs, one a full egg in a Ziploc bag one egg with caramelized onions that have been caramelized for about two hours maybe if I recall right and that was one yolk and both of the bags with caramelized onions were put in sous vide for about more than six hours overnight. One was cooked at 141.5\u00b0 the..."
    },
    {
      "date": "2025-10-10T18:19:55.509711+00:00",
      "session_id": "1275063227_10102025_181726_554112",
      "message_index": 4,
      "role": "assistant",
      "temp_raw": "145",
      "message": "Thanks for sharing your experiment. It sounds like the 145.5\u00b0F batch turned out thicker with a nicer aroma and flavor than the 141.5\u00b0F one."
    },
    {
      "date": "2025-10-10T18:19:55.509711+00:00",
      "session_id": "1275063227_10102025_181726_554112",
      "message_index": 4,
      "role": "assistant",
      "temp_raw": "141",
      "message": "Thanks for sharing your experiment. It sounds like the 145.5\u00b0F batch turned out thicker with a nicer aroma and flavor than the 141.5\u00b0F one."
    },
    {
      "date": "2025-10-10T18:16:23.945461+00:00",
      "session_id": "1275063227_10102025_181530_475424",
      "message_index": 1,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgEAAxkBAAIJ42jpTT-GyWMYsQdktimPUW5P575NAAIdC2sb871JR1tisaWX-AdiAQADAgADeQADNgQ.jpg]"
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 1,
      "role": "user",
      "temp_raw": "174c",
      "message": "[photo_url: https://storage.googleapis.com/cheftest-f174c/telegram_photos/AgACAgEAAxkBAAIJmWjoKCABkoCj8SaFfjJBW_C7vJH3AAISC2sb871BRwOHDSjJwdieAQADAgADeQADNgQ.jpg]"
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 2,
      "role": "assistant",
      "temp_raw": "200\u00b0F",
      "message": "[media_description: I\u2019m caramelizing some onions. They\u2019ve been cooking about 40 minutes; the pan\u2019s surface temperature has ranged 160\u2013200\u00b0F, which is a bit high, so I\u2019m turning it down.]"
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 4,
      "role": "user",
      "temp_raw": "160",
      "message": "I\u2019m caramelizing some onions. They\u2019ve probably been cooking for about. I don\u2019t know maybe 40 minutes surface. Temperature of the pan goes between 160 and 200. That\u2019s a little too high so I\u2019m gonna turn it down."
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 4,
      "role": "user",
      "temp_raw": "200",
      "message": "I\u2019m caramelizing some onions. They\u2019ve probably been cooking for about. I don\u2019t know maybe 40 minutes surface. Temperature of the pan goes between 160 and 200. That\u2019s a little too high so I\u2019m gonna turn it down."
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 5,
      "role": "assistant",
      "temp_raw": "200\u00b0C",
      "message": "Nice work checking the heat. A gentle, slow caramelization will give you deeper flavor.\n\nQuick tips if you want to salvage and finish nicely:\n- Lower the heat to low or medium-low for a steady, light sizzle (around a gentle simmer). If you\u2019re at 160\u2013200\u00b0C, try closer to low heat and adjust as needed.\n- Stir every few minutes early on to prevent sticking, the..."
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 6,
      "role": "user",
      "temp_raw": "160",
      "message": "I\u2019m caramelizing some onions. They\u2019ve probably been cooking for about. I don\u2019t know maybe 40 minutes surface. Temperature of the pan goes between 160 and 200. That\u2019s a little too high so I\u2019m gonna turn it down."
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 6,
      "role": "user",
      "temp_raw": "200",
      "message": "I\u2019m caramelizing some onions. They\u2019ve probably been cooking for about. I don\u2019t know maybe 40 minutes surface. Temperature of the pan goes between 160 and 200. That\u2019s a little too high so I\u2019m gonna turn it down."
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 7,
      "role": "assistant",
      "temp_raw": "200\u00b0C",
      "message": "Got it \u2014 you\u2019ve been caramelizing onions for about 40 minutes, with the pan around 160\u2013200\u00b0C, and you\u2019re turning the heat down."
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 8,
      "role": "user",
      "temp_raw": "213\u00b0",
      "message": "Getting the pan right when I getting the pan right is a little tricky so when I have the pan set to the LO setting that\u2019s below two on the left bottom burner the surface temperature of the pan gets hotter. It\u2019s 213\u00b0. I think there\u2019s a lower setting that I\u2019m gonna try but that\u2019s way too hot and this is the this is the heavy large pan."
    },
    {
      "date": "2025-10-09T21:31:26.148533+00:00",
      "session_id": "1275063227_09102025_212452_597702",
      "message_index": 9,
      "role": "assistant",
      "temp_raw": "213\u00b0",
      "message": "Got it \u2014 you\u2019re trying to dial in heat on a heavy pan while caramelizing onions, and the surface is around 213\u00b0 even on LO.\n\nHere are a few quick ways to stabilize the heat, if you\u2019d like to try:\n- Use a heat diffuser or move the pan to a cooler area of the burner to reduce direct heat, aiming for a gentle simmer rather than a sizzle.\n- Stir more frequently..."
    }
  ]
}
END_JSON"""
start = raw.find("BEGIN_JSON") + len("BEGIN_JSON")
end = raw.rfind("END_JSON")
payload = json.loads(raw[start:end].strip())

rows = []
for item in payload.get("candidates", []):
    date = item.get("date") or ""
    temp = item.get("temp_raw") or ""
    msg = (item.get("message") or "").lower()
    outcome = ""
    for key in [
        "burned",
        "burnt",
        "burn",
        "brown",
        "browned",
        "caramel",
        "soft",
        "sweet",
        "nutty",
        "crisp",
        "blacken",
        "bitter",
    ]:
        if key in msg:
            outcome = key
            break
    rows.append((date, temp, outcome))

seen = set()
final = []
for date, temp, outcome in rows:
    key = (date, temp, outcome)
    if key in seen:
        continue
    seen.add(key)
    final.append((date, temp, outcome))

for date, temp, outcome in final:
    print("{} | {} | {}".format(date, temp, outcome))