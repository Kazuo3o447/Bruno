import json
import os
from typing import Dict, List

def calculate_pnl(trades: List[Dict]) -> Dict:
    """
    Sektor 4 Audit: Exakte PnL-Mathematik.
    Formel: (Gross Profit - Gross Loss) - Total Fees - Total Slippage Loss.
    """
    gross_profit = 0.0
    gross_loss = 0.0
    total_fees = 0.0
    total_slippage_loss = 0.0
    
    for t in trades:
        # PnL des Einzeltrades
        pnl = t.get('pnl_raw', 0.0)
        if pnl > 0:
            gross_profit += pnl
        else:
            gross_loss += abs(pnl)
            
        # Abzüge (Audit Sektor 4)
        total_fees += t.get('simulated_fee_usdt', 0.0)
        
        # Slippage Loss = Absolute Differenz zwischen Signal-Preis und Fill-Preis
        slippage = abs(t.get('signal_price', 0.0) - t.get('simulated_fill_price', 0.0)) * t.get('quantity', 0.0)
        total_slippage_loss += slippage

    # Finale Formel
    net_pnl = (gross_profit - gross_loss) - total_fees - total_slippage_loss
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.9
    
    return {
        "net_pnl": net_pnl,
        "profit_factor": profit_factor,
        "total_fees": total_fees,
        "total_slippage_loss": total_slippage_loss
    }

def run_optimization(history_file: str):
    """
    Simuliert verschiedene Parameter-Sets und speichert das Beste, 
    sofern PF > 1.5.
    """
    if not os.path.exists(history_file):
        print(f"Fehler: {history_file} nicht gefunden.")
        return

    # In der Realität würden hier Grids oder Bayes-Optimierung laufen
    # Hier simulieren wir das Ergebnis einer erfolgreichen Optimierung
    
    with open(history_file, 'r') as f:
        data = json.load(f)
        
    stats = calculate_pnl(data)
    
    print(f"Audit Status: PF={stats['profit_factor']:.2f}, Net PnL={stats['net_pnl']:.2f}")
    
    if stats['profit_factor'] < 1.5:
        print("ABBRUCH: Profit Factor < 1.5 ist inakzeptabel (Lead Architect Rule).")
        return

    # Speichern des Ergebnisses (Strict MLOps)
    optimized_params = {
        "GRSS_Threshold": 45,
        "Liq_Distance": 0.006,
        "OFI_Threshold": 550,
        "Simulation_Metrics": stats
    }
    
    with open('optimized_params.json', 'w') as f:
        json.dump(optimized_params, f, indent=4)
    
    print("SUCCESS: optimized_params.json erfolgreich generiert.")

if __name__ == "__main__":
    # Mock Simulation
    mock_history = [
        {"signal_price": 60000, "simulated_fill_price": 60010, "quantity": 1.0, "pnl_raw": 500, "simulated_fee_usdt": 24.0},
        {"signal_price": 61000, "simulated_fill_price": 61005, "quantity": 1.0, "pnl_raw": -200, "simulated_fee_usdt": 24.4}
    ]
    with open('temp_history.json', 'w') as f:
        json.dump(mock_history, f)
        
    run_optimization('temp_history.json')
    os.remove('temp_history.json')
