## ###################################################################################################################
##  Program :   GexLevels
##  Author  :   Sean Burner
##  Detail  :   Main calling function 
##  Install :   
##  Example :
##              python3 
##              python3 
##  Notes   :   https://docs.python.org/3/tutorial/classes.html
## #############################################################################
import sys 
import getpass
import inspect
from src.BarChartAPI        import BarChartAPI
from src.Calculations       import Calculations
from src.TradingViewPayload import TradingViewPayload 
    

def GexLevels ()->str:
    """
        Main instructions to get a supplied symbol's spot price and its market data from Barchart.com to build GEX levels for TradingView
        PARAMETERS :
                        None 
        RETURNS    : 
                        str - TradingView formatted string for indicator
    """
    tvString  = "[!] Error: No market data retrieved." 
    try:
        ticker      = input("Enter Symbol (e.g. SPX, AAPL, ESM26): ").strip().upper()
        calc        = Calculations()
        barChart    = BarChartAPI( symbol = ticker )
        tvPayload   = TradingViewPayload()

        spot  = barChart.SpotPrice()
        if spot is None :        
            spot = input("Did not get spot , please provide : ").strip()
            spot = float(spot.replace(',', '')) 
        if not spot:
            print("[!] Error: No spot price found. Check symbol or connectivity.")
            sys.exit()
        
        print(f"[*] Analysis Price: ${spot:,.2f}")
        raw_df = barChart.MarketData()
        
        if not raw_df.empty:
            df = calc.Greeks_And_Gex( df=raw_df, spot=spot)
            print(f"[SUCCESS] {len(df)} active contracts processed.")
            df.to_csv( f"data/{ticker}.csv")
            
            # Debugging check for specific high-value strikes if applicable
            #target_strike = 7000.0
            #if not df[df['strikeprice'] == target_strike].empty:
            #     print(f"DEBUG: [main] Strike {target_strike} data found.")
            
            tvString = tvPayload.Build(data=df, symbol=ticker, spot=spot)
        
    except: 
            print("\t\t|EXCEPTION: GexLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
                
    return tvString


if __name__ == "__main__":

    tvString =  GexLevels()
    
    print("\n--- TRADINGVIEW PAYLOAD ---")
    print(tvString  )   
