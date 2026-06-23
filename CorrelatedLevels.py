## ###################################################################################################################
##  Program :   Correlated Gex Levels 
##  Author  :   Sean Burner
##  Detail  :   Analyze the Gex levels for several related assets ( SPY/SPX/ESMXX) to find Confluence levels 
##  Install :   
##  Example :
##              python3 
##              python3 
##  Notes   :   https://docs.python.org/3/tutorial/classes.html
## #############################################################################
import re 
import sys
import getpass
import inspect

import pandas                   as pd
import numpy                    as np
    
from pathlib                    import Path

src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
    
from src.BarChartAPI            import BarChartAPI
from src.Calculations           import Calculations
from src.ConfluenceEngine       import ConfluenceEngine 
from src.TradingViewPayload     import TradingViewPayload





def UseDataFiles()->str:
    """
        Use data  files (.rtf ) that already contain the GEX strings
        PARAMETERS  :
        RETURNS     :
                        str - consolidated TradingView String
    """   
    from  wakepy  import keep
    
    files       = None 
    data        = {}
    base        = ""
    spots       = {'ESM26': 7494.75,   'SPY': 746.48, 'SPX':7481.0} # testing 
    confl       = ConfluenceEngine(proximity_threshold_points=12.0)
    tvString    = ""
    tvPayload   = TradingViewPayload()
    benchmarks  = None 
    
    try:
        print("\t\t Using Data Files as input   ")
        dirPath             = input("Where are the data files located: " )
        fileExt             = input("What is the file extension for the data file(s) [csv, dat,rtf ] : ")            
        files               =  {f.stem:f  for f in Path(dirPath).iterdir()  if f.suffix =="."+fileExt }        
        data.update( { key: confl.LoadFileData( fileName=value) for key,value in files.items() }  )

        while  not ( base in list( files.keys() ) ) :
            base                = input(f"Which symbol to use as the base chart :  {list( files.keys() )}  ")
                                    
            if not ( base in list( files.keys() ) ) :
                print(f"That was not an appropriate choice : {base }")
                return tvString
        
              
        for sym in data:
            barChart            = BarChartAPI( symbol = sym )
            data[sym].update( { 'spot' :  barChart.SpotPrice() })
        #    data[sym].update( { 'spot' : spots[sym] }) #  TEST MODE barChart.SpotPrice()
        #print( data )    
        data, benchMarks    = confl.NormalizeValues( data ,base )       
        data                = confl.ConsolidateLevels( data, base )
        tvString            = tvPayload.TvStringFromDict( data, benchMarks )

        #with keep.presenting():
        #    print("Keeping the screen active ")
    except:
        print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
        for entry in sys.exc_info():
            print("\t\t >>   " + str(entry) )

    return tvString



def UserProvidedSymbols()-> str :
    """
        Orchestrator for getting list of symbols from user to correlate
        PARAMETERS  :
                        None
        RETURNS     :
                        str - TradingView GEX Indicator formatted string
    """
    import pickle
    base            = ''
    data            = {}
    calc            = Calculations()
    confl           = ConfluenceEngine(proximity_threshold_points=12.0)
    tickers         = []
    tvString        = ""
    is_future       = False
    defaultDF       = { 'strikeprice':0, 'liquidity':0 }
    tvPayload       = TradingViewPayload()
    test_ticker     = [ ['ESM26', 7590.25], ['SPY', 755.78], ['SPX', 7582.36] ]  # test 
    master_levels   = []
    try:
        print("\t\t Getting input from User  ")
        
        tickerFromUser  = input ("Provide assets to be correlated separated by commmas: " )
        symbols         = tickerFromUser.split(",")
        base            = symbols[0]
        
        # Get SPOT , for better multiplier calc do it as quickly as possible 
        for pos, ticker in enumerate(symbols):
            barChart    = BarChartAPI( symbol = ticker )
            spot        = barChart.SpotPrice()
            temp        = [ ticker, spot]            
            tickers.append( temp )
            print(f"[ * ] Getting Spot for : {ticker} -> ${spot}")

        #Get Market Data
        cw_data = pd.DataFrame( )       
        pw_data = pd.DataFrame( )
        print(f"[DEBUG] TICKERS : {tickers}")
        for pos, ticker in enumerate(tickers):            
            barChart    = BarChartAPI( symbol = tickers[pos][0] )
            df          = barChart.MarketData()
                    
            #with open(f"data/{ticker[0]}.pkl", "wb") as file :
            #    pickle.dump( df, file )
                
            #with open(f"data/{ticker[0]}.pkl", "rb") as file :
            #    df = pickle.load(  file )                           

            spot            = ticker[1]
            df['source']    = ticker[0]
            df              = calc.Greeks_And_Gex( df=df , spot=tickers[pos][1])            
            df              = calc.DataCleaning( df=df)
            df, is_future   = calc.FuturesStrikePrice(symbol=ticker[0], data=df, spot=ticker[1])
            if pos == 0: # ONLY CALCULATE FOR BASE ASSET
                print(f"[DEBUG] {base} SPOT : {spot} ")
                eh, el , em_dist   = calc.ExpectedHighLow( spot=spot)
                zg_strike          = calc.ZG_Strike( spot =spot, df =df , eh=eh, el=el )
                print(f"[DEBUG] {base} ZG STRIKE : {zg_strike} ")
                vh , vl            = calc.VolatilityHighLow( zg_strike=zg_strike,spot=spot, em_dist=em_dist) 
                                   
            cw_data, pw_data    = calc.WallsData(df =df, spot=spot)
            
            #with open(f"data/{ticker[0]}_cw.pkl", "rb") as file :
            #    cw_data = pickle.load(  file )
            #with open(f"data/{ticker[0]}_pw.pkl", "rb") as file :
            #    pw_data = pickle.load(  file )
            
            #with open(f"data/{ticker[0]}_cw.pkl", "wb") as file :
            #    pickle.dump( cw_data, file )
            #with open(f"data/{ticker[0]}_pw.pkl", "wb") as file :
            #    pickle.dump( pw_data, file )
            
            temp    = confl.BuildDictFromData( ticker = ticker, cw_data=cw_data, pw_data=pw_data, zg_strike=zg_strike, eh=eh,el=el, vh=vh, vl=vl)
            
            #df.to_csv( f"data/{ticker[0]}.csv")

            data.update( {ticker[0] : temp } )
            data[ticker[0]].update( { 'source': ticker[0], 'spot' :  ticker[1] })
        
        data, benchMarks    = confl.NormalizeValues( data ,base )       
        data                = confl.ConsolidateLevels( data, base )
        tvString            = tvPayload.TvStringFromDict( data, benchMarks )

  
    except:
        print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
        for entry in sys.exc_info():
            print("\t\t >>   " + str(entry) )

    return tvString 



def main() -> str :
    """
        Driving logic to find confluence levels
        PARAMETERS :
                        None 
        RETURNS    :
                        None
    """
    tvString  = ""
    
    try:
        decision        = input("Input [S]ymbols or use [D]ata files?  ")
        if decision.upper() == 'D' :
            tvString = UseDataFiles()
        elif decision.upper() != 'S' :
            print("That was not one of the choices.")
        else:
            tvString = UserProvidedSymbols()
        
        print(f"\n\t********************* TRADING VIEW *************************\n{tvString}")
        
    except:
            print("\t\t|EXCEPTION: CorrelatedLevels::" + str(inspect.currentframe().f_code.co_name) + " - Ran into an exception:" )
            for entry in sys.exc_info():
                print("\t\t >>   " + str(entry) )
                
    return tvString 


if __name__ == "__main__":
    main()
