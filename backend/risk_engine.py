def calculate_risk(people_count : int  , capacity : int):
    if capacity <= 0 :
        return {
            "Occupancy" : 0 ,
            "risk" : "UNKNOWN"
        }
    
    occupancy = (people_count / capacity) * 100
    
    if occupancy < 40:
        risk = "LOW"
        
    elif occupancy < 70:
        risk = "MODERATE"
        
    elif occupancy < 90:
        
        risk = "HIGH"
        
    else : 
        risk  = "CRITICAL"
        
    return {"Occupancy" : round(occupancy , 2) ,
            "risk" : risk}
    