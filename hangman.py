import random

words = """ orange raspberry pineapple apricot coconut pomegranate"""
words = words.split()
secret_word = random.choice(words)
display = ["_"] * len(secret_word)
chance = 6 # number of chances for the user
guessed_letters = set()

print(f'HANGMAN! Guess the secret word (fruit) one letter at a time, its length is: {len(secret_word)}. You have {chance} guesses left')

while True:
    # Show the current progress of the word to the player
    print("Current word:", " ".join(display))
    str_guess = input("Guess a letter: ").lower()
    correct = True
    if str_guess == secret_word:
        print("Correct! The word was:", secret_word)
        break
    if not str_guess.isalpha():
        print('Enter only a letter!')
        continue
    if len(str_guess) != 1:
        print("Enter only ONE letter!\n")
        continue
        # --- NEW: block repeated guesses ---
    if str_guess in guessed_letters:
        print("You already guessed that letter. Try a new one.\n")
        continue
    guessed_letters.add(str_guess)

    # Loop through each position in the secret word
    if str_guess in secret_word:
        for i in range(len(secret_word)):
            if secret_word[i] == str_guess:
                display[i] = str_guess
                correct = True
        print("correctly guessed!")
    else:
        chance -= 1
        print(f' Nope. You have {chance} guesses left')

    if "_" not in display:
        print("YOU WIN!")
        print("The word was:", secret_word)
        break

    if chance == 0:
        print(f'YOU LOST! The word was {secret_word}')
        break

if __name__ == '__main__':
    print(f'HANGMAN GAME COMPLETED!')