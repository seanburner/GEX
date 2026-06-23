## ###################################################################################################################
##  Program :   GEX_Test
##  Author  :   Sean A. Burner
##  Install :   pip3 install requests  inspect platform argparse 
##  Example :	Scaffolding for tests 
##  Notes   :
## ###################################################################################################################import pytest
from src.ConfluenceEngine       import UseDataFiles
from src.Calculations           import Calculations
from src.TradingViewPayload     import TradingViewPayload


def test_data_file_conversion():   
   result   = ("L:7360.0,ZG,ZERO GAMMA,Zero Gamma~Dealer gamma flips here~Price magnet CW=0.0M | PW=8.2M;7550.0,MP,MAX PAIN,Max Pain~Strike with max OI~Expiry target CW=2524.5M | PW=113.8M;"+
               "7600.0,EH,EM HIGH,Expected Move HIGH~1-sigma upper bound CW=379.4M | PW=0.0M;7350.0,EL,EM LOW,Expected Move LOW~1-sigma lower bound CW=0.0M | PW=79.1M;" +
               "7422.5,VH,VOL HIGH,Vol Band HIGH~ZG + 25% EM CW=0.0M | PW=73.7M;7297.5,VL,VOL LOW,Vol Band LOW~ZG - 25% EM CW=0.0M | PW=0.0M;"+
               "7500.0,CW,Call Wall,CW=829.6M | PW=252.4M  Strength:5 Source:ESM26/SPY/SPY/SPY;7525.0,CW,Call Wall,CW=423.0M | PW=0.0M  Strength:3 Source:ESM26/SPX/SPY;"+
               "7540.0,CW,Call Wall,CW=375.1M | PW=0.0M  Strength:3 Source:ESM26/SPX/SPX;7450.0,PW,Put Wall,CW=0.0M | PW=93.1M  Strength:1 Source:ESM26;"+
               "7400.0,PW,Put Wall,CW=0.0M | PW=111.4M  Strength:3 Source:ESM26/SPX/SPY;7463.69,CW,Call Wall,CW=9.8M | PW=0.0M  Strength:1 Source:SPX;"+
               "7563.88,CW,Call Wall,CW=4.7M | PW=0.0M  Strength:1 Source:SPX;7223.25,PW,Put Wall,CW=0.0M | PW=10.6M  Strength:1 Source:SPX;7329.29,PW,Put Wall,CW=0.0M | PW=17.5M  Strength:1 Source:SPY;7379.49,PW,Put Wall,CW=0.0M | PW=16.8M  Strength:1 Source:SPY")
   tvString =  UseDateFiles()
   assert f"{tvString}" == "{result}"

def test_user_input():   
   result   = ("L:7500.0,ZG,ZERO GAMMA,Zero Gamma~Dealer gamma flips here~Price magnet CW=0.0M | PW=0.0M;7677.89,EH,EM HIGH,Expected Move HIGH~1-sigma lower bound CW=0.0M | PW=0.0M;" +
                "7486.83,EL,EM LOW,Expected Move LOW~1-sigma lower bound CW=0.0M | PW=9.0M;7606.24,VH,VOL HIGH,Vol Band HIGH~ZG + 25% EM CW=15.9M | PW=0.0M;" +
                 "7476.12,VL,VOL LOW,Vol Band Low~ZG + 25% EM CW=0.0M | PW=0.0M;8000.0,CW,Call Wall,CW=11.9M | PW=0.0M  Strength:2 Source:ESM26/SPX;" +
                  "7808.12,CW,Call Wall,CW=20.3M | PW=0.0M  Strength:1 Source:SPX;7708.01,CW,Call Wall,CW=13.0M | PW=0.0M  Strength:1 Source:SPX;7858.17,CW,Call Wall,CW=12.2M | PW=0.0M  Strength:1 Source:SPX;"+
                  "7407.7,PW,Put Wall,CW=0.0M | PW=17.6M  Strength:1 Source:SPX;7307.6,PW,Put Wall,CW=0.0M | PW=9.4M  Strength:1 Source:SPX;7557.86,PW,Put Wall,CW=0.0M | PW=8.8M  Strength:1 Source:SPX")
   tvString =   UserProvidedSymbols()
   assert f"{tvString}" == "{result}"
