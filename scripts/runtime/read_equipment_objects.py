"""Read-only equipment capture CLI, preserving the successful native-object method.

--max-nodes counts visited nodes (including failed captures); default 256, hard
limit 2048. New output directory per run; cycle/link/mapping/budget guards live
in bounded_equipment_reader.py. Null tail is loaded-container coverage only.
The original five-record implementation is retained in the private baseline.
"""
from bounded_equipment_reader import Reader, main
if __name__ == "__main__":
    main()
