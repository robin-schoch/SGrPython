import os

# script to evaluate PowerMeterLog and saves it in a result file

eventFilePath = "C:/Users/sersc/OneDrive - FHNW/5 Semester/P5/01_Eigene_Dokumente/Logs/VerbindungstestABBPowermeter/8hTest/Events.txt"
file = open(eventFilePath, "r")
data = file.read()
resultFilePath = os.path.splitext(eventFilePath)[0] + "_Result.txt"

comment = input("Comment the Log:")

# get number of occurrences of the substring in the string
ExceptionOnOne = data.count("Exception has occurred on Sensor 1")
ExceptionOnZero = data.count("Exception has occurred on Sensor 0")
successOnOne = data.count("Retry 1 was successful")
successOnTwo = data.count("Retry 2 was successful")
successOnThree = data.count("Retry 3 was successful")
successOnFour = data.count("Retry 4 was successful")
successOnFive = data.count("Retry 5 was successful")
abort = data.count("while loop abort")
lastOccurrenceIndex = data.rfind("Iteration:")
startIndex = lastOccurrenceIndex + 11
endIndex = data.index(" ", startIndex, startIndex + 10)
iterations = data[startIndex:endIndex]

with open(resultFilePath, "w") as ResultFile:
    ResultFile.write(comment + "\n")
    print(comment)
    ResultFile.write(f"Number of iterations: {iterations}\n")
    print(f"Number of iterations: {iterations}")
    ResultFile.write(f"Exception on ABB uni: {ExceptionOnZero}\n")
    print(f"Exception on ABB uni: {ExceptionOnZero}")
    ResultFile.write(f"Exception on ABB bi: {ExceptionOnOne}\n")
    print(f"Exception on ABB bi: {ExceptionOnOne}")
    ResultFile.write(f"Success on first retry: {successOnOne}\n")
    print(f"Success on first retry: {successOnOne}")
    ResultFile.write(f"Success on second retry: {successOnTwo}\n")
    print(f"Success on second retry: {successOnTwo}")
    ResultFile.write(f"Success on third retry: {successOnThree}\n")
    print(f"Success on third retry: {successOnThree}")
    ResultFile.write(f"Success on fourth retry: {successOnFour}\n")
    print(f"Success on fourth retry: {successOnFour}")
    ResultFile.write(f"Success on fifth retry: {successOnFive}\n")
    print(f"Success on fifth retry: {successOnFive}")
    ResultFile.write(f"Aborts: {abort}\n")
    print(f"Aborts: {abort}")
