/**
 * Tenant Admin - Currency Auto-population
 * Automatically populates currency symbol when currency is selected
 */

(function() {
    'use strict';
    
    // Currency symbol mapping
    const CURRENCY_SYMBOLS = {
        'USD': '$',
        'CAD': 'C$',
        'GBP': '£',
        'EUR': '€',
        'AUD': 'A$',
        'NGN': '₦',
        'ZAR': 'R',
        'KES': 'KSh',
        'GHS': 'GH₵',
        'UGX': 'USh',
        'TZS': 'TSh',
        'EGP': 'E£',
        'MAD': 'DH',
        'JPY': '¥',
        'CNY': '¥',
        'INR': '₹',
        'CHF': 'CHF',
    };
    
    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {
        // Find currency and currency_symbol fields
        const currencyField = document.querySelector('#id_currency');
        const currencySymbolField = document.querySelector('#id_currency_symbol');
        
        if (!currencyField || !currencySymbolField) {
            return; // Fields not found, exit
        }
        
        // Function to update currency symbol
        function updateCurrencySymbol() {
            const selectedCurrency = currencyField.value;
            
            if (selectedCurrency && CURRENCY_SYMBOLS[selectedCurrency]) {
                // Only auto-populate if field is empty or has default value
                const currentSymbol = currencySymbolField.value.trim();
                
                if (!currentSymbol || currentSymbol === '$' || currentSymbol === '₦') {
                    currencySymbolField.value = CURRENCY_SYMBOLS[selectedCurrency];
                    
                    // Visual feedback
                    currencySymbolField.style.backgroundColor = '#d1fae5';
                    setTimeout(function() {
                        currencySymbolField.style.backgroundColor = '';
                    }, 1000);
                }
            }
        }
        
        // Listen for currency changes
        currencyField.addEventListener('change', updateCurrencySymbol);
        
        // Also trigger on page load if currency is set but symbol is default
        if (currencyField.value) {
            const currentSymbol = currencySymbolField.value.trim();
            if (!currentSymbol || currentSymbol === '$') {
                updateCurrencySymbol();
            }
        }
        
        // Add helper text
        const symbolFieldWrapper = currencySymbolField.closest('.form-row') || 
                                    currencySymbolField.closest('.field-currency_symbol');
        
        if (symbolFieldWrapper) {
            const helpText = document.createElement('div');
            helpText.className = 'help';
            helpText.style.cssText = 'color: #6b7280; font-size: 12px; margin-top: 4px;';
            helpText.innerHTML = '💡 Symbol auto-populates when you select a currency. You can customize it if needed.';
            
            // Only add if not already present
            if (!symbolFieldWrapper.querySelector('.help')) {
                symbolFieldWrapper.appendChild(helpText);
            }
        }
    });
})();