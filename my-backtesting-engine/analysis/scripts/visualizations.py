"""
Visualization Helpers - Functions for creating charts and plots
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional, List, Tuple
from pathlib import Path


class ChartHelper:
    """Helper class for creating charts and visualizations."""
    
    def __init__(self, output_dir: str = "analysis/outputs/charts"):
        """
        Initialize chart helper.
        
        Args:
            output_dir: Directory to save charts
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (14, 7)
    
    def plot_price_history(
        self,
        df: pd.DataFrame,
        title: str = "Price History",
        save_as: Optional[str] = None
    ):
        """
        Plot price history with volume.
        
        Args:
            df: DataFrame with date, close, volume columns
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), 
                                        gridspec_kw={'height_ratios': [3, 1]})
        
        # Price plot
        ax1.plot(df['date'], df['close'], linewidth=2, label='Close Price')
        ax1.set_title(title, fontsize=16, fontweight='bold')
        ax1.set_ylabel('Price (₹)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Volume plot
        ax2.bar(df['date'], df['volume'], alpha=0.5, color='blue')
        ax2.set_ylabel('Volume', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_with_indicators(
        self,
        df: pd.DataFrame,
        indicators: List[str],
        title: str = "Price with Indicators",
        save_as: Optional[str] = None
    ):
        """
        Plot price with technical indicators.
        
        Args:
            df: DataFrame with price and indicator columns
            indicators: List of indicator column names to plot
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # Plot price
        ax.plot(df['date'], df['close'], linewidth=2, label='Close Price', color='black')
        
        # Plot indicators
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        for idx, indicator in enumerate(indicators):
            if indicator in df.columns:
                color = colors[idx % len(colors)]
                ax.plot(df['date'], df[indicator], linewidth=1.5, 
                       label=indicator, color=color, alpha=0.7)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_ylabel('Price (₹)', fontsize=12)
        ax.set_xlabel('Date', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_rsi(
        self,
        df: pd.DataFrame,
        rsi_column: str = 'rsi',
        title: str = "RSI Indicator",
        save_as: Optional[str] = None
    ):
        """
        Plot RSI with overbought/oversold levels.
        
        Args:
            df: DataFrame with date and RSI columns
            rsi_column: Name of RSI column
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                        gridspec_kw={'height_ratios': [2, 1]})
        
        # Price plot
        ax1.plot(df['date'], df['close'], linewidth=2, color='black')
        ax1.set_title(title, fontsize=16, fontweight='bold')
        ax1.set_ylabel('Price (₹)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        
        # RSI plot
        ax2.plot(df['date'], df[rsi_column], linewidth=2, color='purple')
        ax2.axhline(y=70, color='r', linestyle='--', label='Overbought (70)')
        ax2.axhline(y=30, color='g', linestyle='--', label='Oversold (30)')
        ax2.fill_between(df['date'], 70, 100, alpha=0.1, color='red')
        ax2.fill_between(df['date'], 0, 30, alpha=0.1, color='green')
        ax2.set_ylabel('RSI', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylim(0, 100)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_macd(
        self,
        df: pd.DataFrame,
        title: str = "MACD Indicator",
        save_as: Optional[str] = None
    ):
        """
        Plot MACD indicator.
        
        Args:
            df: DataFrame with date, close, macd columns
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                        gridspec_kw={'height_ratios': [2, 1]})
        
        # Price plot
        ax1.plot(df['date'], df['close'], linewidth=2, color='black')
        ax1.set_title(title, fontsize=16, fontweight='bold')
        ax1.set_ylabel('Price (₹)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        
        # MACD plot
        ax2.plot(df['date'], df['macd'], linewidth=2, label='MACD', color='blue')
        ax2.plot(df['date'], df['macd_signal'], linewidth=2, label='Signal', color='red')
        ax2.bar(df['date'], df['macd_histogram'], alpha=0.3, label='Histogram', color='gray')
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax2.set_ylabel('MACD', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_bollinger_bands(
        self,
        df: pd.DataFrame,
        title: str = "Bollinger Bands",
        save_as: Optional[str] = None
    ):
        """
        Plot Bollinger Bands.
        
        Args:
            df: DataFrame with date, close, bb_upper, bb_middle, bb_lower columns
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, ax = plt.subplots(figsize=(14, 7))
        
        # Plot bands
        ax.plot(df['date'], df['bb_upper'], linewidth=1, label='Upper Band', 
               color='red', linestyle='--')
        ax.plot(df['date'], df['bb_middle'], linewidth=1, label='Middle Band', 
               color='blue', linestyle='--')
        ax.plot(df['date'], df['bb_lower'], linewidth=1, label='Lower Band', 
               color='green', linestyle='--')
        
        # Fill between bands
        ax.fill_between(df['date'], df['bb_upper'], df['bb_lower'], alpha=0.1, color='gray')
        
        # Plot price
        ax.plot(df['date'], df['close'], linewidth=2, label='Close Price', color='black')
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_ylabel('Price (₹)', fontsize=12)
        ax.set_xlabel('Date', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_equity_curve(
        self,
        df: pd.DataFrame,
        title: str = "Equity Curve",
        save_as: Optional[str] = None
    ):
        """
        Plot backtest equity curve.
        
        Args:
            df: DataFrame with date and total_capital columns
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ax.plot(df['date'], df['total_capital'], linewidth=2, color='green')
        ax.fill_between(df['date'], df['total_capital'], 
                       alpha=0.2, color='green')
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_ylabel('Portfolio Value (₹)', fontsize=12)
        ax.set_xlabel('Date', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add return percentage
        initial = df.iloc[0]['total_capital']
        final = df.iloc[-1]['total_capital']
        total_return = ((final - initial) / initial) * 100
        
        ax.text(0.02, 0.98, f'Total Return: {total_return:.2f}%',
               transform=ax.transAxes, fontsize=12, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_returns_distribution(
        self,
        returns: pd.Series,
        title: str = "Returns Distribution",
        save_as: Optional[str] = None
    ):
        """
        Plot returns distribution histogram.
        
        Args:
            returns: Series of returns
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ax.hist(returns.dropna(), bins=50, alpha=0.7, color='blue', edgecolor='black')
        ax.axvline(returns.mean(), color='red', linestyle='--', 
                  linewidth=2, label=f'Mean: {returns.mean():.4f}')
        ax.axvline(0, color='black', linestyle='-', linewidth=1)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xlabel('Returns', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_correlation_matrix(
        self,
        df: pd.DataFrame,
        columns: List[str],
        title: str = "Correlation Matrix",
        save_as: Optional[str] = None
    ):
        """
        Plot correlation matrix heatmap.
        
        Args:
            df: DataFrame with data
            columns: List of columns to include
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, ax = plt.subplots(figsize=(10, 8))
        
        corr = df[columns].corr()
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', 
                   center=0, ax=ax, square=True)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def plot_comparison(
        self,
        dfs: List[pd.DataFrame],
        labels: List[str],
        value_column: str = 'close',
        title: str = "Comparison",
        save_as: Optional[str] = None
    ):
        """
        Plot comparison of multiple stocks/strategies.
        
        Args:
            dfs: List of DataFrames
            labels: List of labels for each DataFrame
            value_column: Column to plot
            title: Chart title
            save_as: Filename to save (optional)
        """
        fig, ax = plt.subplots(figsize=(14, 7))
        
        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
        
        for idx, (df, label) in enumerate(zip(dfs, labels)):
            # Normalize to percentage returns
            normalized = (df[value_column] / df[value_column].iloc[0] - 1) * 100
            color = colors[idx % len(colors)]
            ax.plot(df['date'], normalized, linewidth=2, label=label, color=color)
        
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_ylabel('Returns (%)', fontsize=12)
        ax.set_xlabel('Date', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        
        plt.tight_layout()
        
        if save_as:
            plt.savefig(self.output_dir / save_as, dpi=300, bbox_inches='tight')
        
        plt.show()
