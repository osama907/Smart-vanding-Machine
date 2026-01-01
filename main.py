# from functional_calling_database import handle_conversation
# from voice_module import record_audio, speech_to_text, text_to_speech
# from vision import person_des

# image_path = "https://th.bing.com/th/id/OIP.gYYQ7lZOpDWKgWRmNZymNgHaEJ?w=318&h=180&c=7&r=0&o=5&dpr=1.1&pid=1.7"


# while True:
#     # audio_file = record_audio(duration=7) 

#     # text = speech_to_text(audio_file)

#     text = input('\nUser Message: ')

#     u_d = person_des(image_path)

#     text += f" Image description of the person: {u_d}"

#     print(f"\nDEBUG: {text}\n")

    

#     llm_response = handle_conversation(text)

#     # text_to_speech(llm_response)


from functional_calling_database import handle_conversation
from vision import person_des
#image_path = "https://th.bing.com/th/id/OIP.gYYQ7lZOpDWKgWRmNZymNgHaEJ?w=318&h=180&c=7&r=0&o=5&dpr=1.1&pid=1.7"


#image_description = person_des(image_path)

#first_message = True

while True:
    user_text = input('\nUser Message: ').strip()
    if not user_text:
        print("Please enter some text!")
        continue
    # if first_message:
    #     prompt = f"{user_text} Image description of the person: {image_description}"
    #     # print(f"\nUser Message: {user_text}\n")
    #     print(f"According to image description: {image_description}\n")
    #     first_message = False
    else:
        prompt = user_text
        # print(f"\nUser Message: {user_text}\n")
    llm_response = handle_conversation(prompt)
    print(f"AI Response:\n{llm_response}\n")