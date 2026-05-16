class flashcard:
    def __init__(self, question, answer):
        self.question = question
        self.answer = answer

flash_cards = {
    'What is the largest continent': 'Asia',
    'What is the 7th planet from the Sun': 'Uranus',
    'What is the capital of Nebraska': 'Lincoln'
}

def show_menu():
    print(">> 1. Quiz Me")
    print(">> 2. Add a flashcard - question + answer")
    print(">> 3. EXIT\n")

def main():
    while True: # will run
        show_menu() # opens the show menu with the 3 outputs
        f_input = input(">> Press enter 1 through 3 from the menu above: ") #asking for user input

        if f_input == "1": #if user inputs int 1 --> Quiz starts
            score = 0  # start with a zero score
            for question,answer in flash_cards.items():
                print(question)
                user_input = input(">> What is your answer: ")
                if user_input.lower() == answer.lower():
                    score += 1
            print(f"You got {score} / {len(flash_cards)}\n")

        elif f_input == "2": #add a flashcard to the dictionary
            add_card_question = input('Please enter your flashcard question: ')
            add_card_answer = input('Please enter your flashcard answer: ')
            flash_cards[add_card_question] = add_card_answer
            print('Flashcard was added to the end!') # flash card addition will delete after loop ends

        elif f_input == "3": #exit the program as user picked 3
            print(">> EXITING PROGRAM\n")
            break

        else: #invalid answer. ask if they want to try again or end
            looper = input(">> Invalid input. Would you like to try again? (y/n)\n")
            if looper.lower() in ["y", "ye", "yea", "yeah", "yes"]:
                continue
            else:
                print(">> EXITING PROGRAM\n")
                break

if __name__ == "__main__":
    main()