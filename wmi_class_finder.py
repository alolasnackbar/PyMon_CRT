import wmi

def find_thermal_wmi_classes():
    """
    Connects to the root\wmi namespace and lists all classes
    that might contain temperature data, then attempts to query them.
    """
    try:
        c = wmi.WMI(namespace="root\wmi")
        print("Searching for WMI classes related to 'temperature' or 'thermal'...")
        all_classes = [cls for cls in c.classes]

        found_classes = [
            cls for cls in all_classes
            if "temperature" in cls.lower() or "thermal" in cls.lower()
        ]

        if found_classes:
            print("\nFound the following WMI classes:")
            for cls_name in found_classes:
                print(f"- {cls_name}")
            
            print("\n--- Querying found classes for data ---")
            for cls_name in found_classes:
                try:
                    query_result = c.query(f"SELECT * FROM {cls_name}")
                    if query_result:
                        print(f"\nData found in '{cls_name}':")
                        for item in query_result:
                            # Print all attributes and their values
                            for prop in item.properties:
                                value = getattr(item, prop)
                                print(f"  - {prop}: {value}")
                    else:
                        print(f"\nClass '{cls_name}' is empty or contains no data.")
                except Exception as query_error:
                    print(f"\nCould not query class '{cls_name}': {query_error}")
        else:
            print("\nNo WMI classes related to 'temperature' or 'thermal' were found in 'root\wmi'.")
            print("Your hardware may not expose temperature data via this WMI namespace.")
            print("You may need to use a different method or library to get temperature data.")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure the 'wmi' library is installed (`pip install wmi`).")

if __name__ == "__main__":
    find_thermal_wmi_classes()
