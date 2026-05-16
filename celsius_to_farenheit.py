# This is a Celsius to F or vice versa
# can use import tkinter as tk + from tkinter import messagebox if want clickable boxes but add code

# This is the menu below with 3 options to choose from
def show_menu():
    print("1. Convert from Celsius to Fahrenheit") # C --> F
    print("2. Convert from Fahrenheit to Celsius") # F --> C
    print("3. QUIT and END this program.") # ❌ user would like out
# in the main function need something in case user doesn't input integers 1 through 3

# for returning F
def c_to_f(c):
    return (c * 1.8) + 32

# for returning C
def f_to_c(f):
    return (f - 32) / 1.8

def main():
    while True:
        show_menu()
        choice = input("\n>> Enter your choice from the menu (1--> 3): ")

        if choice == "1": #need to prompt the user to give Celsius(c) and call c_to_f
            c_input = input("Enter Celsius to Fahrenheit: ")
            c = float(c_input)
            c_output = c_to_f(c)
            print(f'The conversion was successfully converted from {c_input} Celsius to {round(c_output,2)} Fahrenheit!\n')
        elif choice == "2": #need to prompt the user to give Fahrenheit(f) and call f_to_c
            f_input = input("Enter Fahrenheit to Celsius: ")
            f = float(f_input)
            f_output = f_to_c(f)
            print(f'The conversion was successfully converted from {f_input} Fahrenheit to {round(f_output,2)} Celsius!\n')
        elif choice == "3":
            print("Quitting this program ASAP")
            break
        else:
            looper = input("\n>> Invalid choice. Would you like to continue? (y/n): ")
            if looper.lower() in ['y','ye','yea','yeah','yes']:
                continue
            else:
                print('Ending this program ASAP')
                break

if __name__ == "__main__":
    main()