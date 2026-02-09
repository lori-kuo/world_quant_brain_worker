"""
Alpha Miner Blueprint - AI-powered alpha discovery and optimization
"""
import os
import sys
import json
import logging
import traceback
import requests
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

# Add parent directory to path to import ace_lib
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

try:
    from ace_lib import SingleSession, create_alpha, get_user_profile, simulate_alpha
    from helpful_functions import get_all_alphas_stats
except ImportError:
    print("Warning: Could not import ace_lib or helpful_functions")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

brain_api_url = os.environ.get("BRAIN_API_URL", "https://api.worldquantbrain.com")

alpha_miner_bp = Blueprint('alpha_miner', __name__)

# Cache for resources
CACHE = {
    'datasets': None,
    'operators': None,
    'user_profile': None,
    'last_update': None
}

def load_user_config_credentials():
    """Load credentials from user_config.json in the untracked folder."""
    try:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        untracked_dir = os.path.dirname(app_dir)
        config_path = os.path.join(untracked_dir, 'user_config.json')

        if not os.path.exists(config_path):
            return None, None

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            credentials = config.get('credentials', {})
            email = credentials.get('email')
            password = credentials.get('password')
            return email, password
    except Exception as e:
        logger.error(f"Error loading user_config.json: {e}")
        return None, None

def create_brain_session():
    """Create a SingleSession using credentials from user_config.json."""
    email, password = load_user_config_credentials()
    if not email or not password:
        raise ValueError('Username and password are required. Please check user_config.json')
    s = SingleSession()
    s.auth = (email, password)

    auth_response = s.post(f"{brain_api_url}/authentication")
    if auth_response.status_code not in [200, 201]:
        raise ValueError(f"Authentication failed: {auth_response.status_code}")

    return s

@alpha_miner_bp.route('/')
def alpha_miner():
    """Render the alpha miner page"""
    return render_template('alpha_miner.html')

@alpha_miner_bp.route('/api/get-resources', methods=['POST'])
def get_resources():
    """Get available datasets, operators, and user info"""
    try:
        # Create session from config
        s = create_brain_session()
        
        resources = {}
        
        # Get datasets
        resources['datasets'] = []
        try:
            # Default filters (match common simulator defaults)
            instrument_type = 'EQUITY'
            region = 'USA'
            delay = '1'
            universe = 'TOP3000'

            url_false = (
                f"https://api.worldquantbrain.com/data-sets?instrumentType={instrument_type}"
                f"&region={region}&delay={delay}&universe={universe}&theme=false"
            )
            url_true = (
                f"https://api.worldquantbrain.com/data-sets?instrumentType={instrument_type}"
                f"&region={region}&delay={delay}&universe={universe}&theme=true"
            )

            response_false = s.get(url_false)
            response_true = s.get(url_true)

            if response_false.status_code == 200:
                datasets_false = response_false.json().get('results', [])
            else:
                datasets_false = []

            if response_true.status_code == 200:
                datasets_true = response_true.json().get('results', [])
            else:
                datasets_true = []

            all_datasets = datasets_false + datasets_true
            resources['datasets'] = all_datasets[:50]
        except Exception as e:
            logger.error(f"Error fetching datasets: {e}")
            resources['datasets'] = []
        
        # Get operators from CSV file
        try:
            operators_file = os.path.join(parent_dir, 'operaters.csv')
            if os.path.exists(operators_file):
                import csv
                operators = []
                with open(operators_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        operators.append({
                            'name': row.get('Operator', ''),
                            'category': row.get('Category', ''),
                            'description': row.get('Description', '')
                        })
                resources['operators'] = operators[:100]  # Limit to 100
            else:
                resources['operators'] = []
        except Exception as e:
            logger.error(f"Error reading operators: {e}")
            resources['operators'] = []
        
        # Get user profile to check available submission types
        try:
            profile_response = s.get('https://api.worldquantbrain.com/users/self')
            if profile_response.status_code == 200:
                profile = profile_response.json()
                resources['user_profile'] = {
                    'username': profile.get('username'),
                    'rank': profile.get('rank'),
                    'can_submit_regular': True,  # All users can submit regular
                    'can_submit_power_pool': profile.get('powerPoolEligible', False),
                }
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            resources['user_profile'] = {
                'can_submit_regular': True,
                'can_submit_power_pool': False
            }
        
        # Get available instruments and regions
        resources['instruments'] = ['EQUITY', 'FUTURES']
        resources['regions'] = ['USA', 'CHN', 'EUR', 'JPN', 'GLB']
        resources['delays'] = [0, 1]
        
        return jsonify({
            'success': True,
            'resources': resources
        })
    
    except Exception as e:
        logger.error(f"Error in get_resources: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alpha_miner_bp.route('/api/generate-alpha', methods=['POST'])
def generate_alpha():
    """Generate alpha expression using AI"""
    try:
        data = request.json
        
        # Get LLM configuration
        provider = data.get('provider', 'ollama')
        model = data.get('model', 'qwen2.5:7b')
        api_key = data.get('api_key', '')
        api_base_url = data.get('api_base_url', 'http://localhost:11434')
        
        # Get generation parameters
        dataset = data.get('dataset', '')
        instrument = data.get('instrument', 'EQUITY')
        region = data.get('region', 'USA')
        delay = data.get('delay', 1)
        strategy_type = data.get('strategy_type', 'momentum')
        
        # Build prompt for AI
        prompt = f"""You are an expert quantitative analyst specializing in WorldQuant BRAIN alpha creation.

Generate a creative and potentially profitable alpha expression using the following constraints:

Dataset: {dataset}
Instrument: {instrument}
Region: {region}
Delay: {delay}
Strategy Type: {strategy_type}

Requirements:
1. Use realistic data fields from the specified dataset (e.g., {dataset}_field1, {dataset}_field2)
2. Incorporate appropriate operators (ts_rank, group_rank, ts_std_dev, etc.)
3. The expression should implement a {strategy_type} strategy
4. Keep complexity moderate (not too simple, not too complex)
5. Consider neutralization and data preprocessing

Output ONLY the alpha expression, nothing else. Example format:
rank(ts_decay_linear(close, 10) / ts_mean(volume, 20))

Your alpha expression:"""

        # Prepare API request
        if provider == 'ollama':
            api_url = f"{api_base_url.rstrip('/')}/v1/chat/completions"
            headers = {'Content-Type': 'application/json'}
        elif provider == 'deepseek':
            api_url = 'https://api.deepseek.com/chat/completions'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        elif provider == 'openai':
            api_url = f"{api_base_url.rstrip('/')}/chat/completions" if api_base_url else 'https://api.openai.com/v1/chat/completions'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown provider: {provider}'
            }), 400
        
        api_data = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 500
        }
        
        # Call AI API
        response = requests.post(api_url, headers=headers, json=api_data, timeout=180)
        
        if response.status_code == 200:
            response_data = response.json()
            alpha_expression = response_data['choices'][0]['message']['content'].strip()
            
            # Clean up the expression
            alpha_expression = alpha_expression.replace('```', '').replace('`', '').strip()
            lines = alpha_expression.split('\n')
            # Take the first non-empty line that doesn't look like markdown
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.lower().startswith('your'):
                    alpha_expression = line
                    break
            
            return jsonify({
                'success': True,
                'expression': alpha_expression,
                'parameters': {
                    'dataset': dataset,
                    'instrument': instrument,
                    'region': region,
                    'delay': delay,
                    'strategy_type': strategy_type
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'AI API error: {response.status_code} - {response.text}'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in generate_alpha: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alpha_miner_bp.route('/api/backtest', methods=['POST'])
def backtest_alpha():
    """Submit alpha for backtesting"""
    try:
        data = request.json
        # Create session from config
        s = create_brain_session()
        
        # Get alpha parameters
        expression = data.get('expression')
        instrument = data.get('instrument', 'EQUITY')
        region = data.get('region', 'USA')
        delay = data.get('delay', 1)
        universe = data.get('universe', 'TOP3000')
        neutralization = data.get('neutralization', 'SUBINDUSTRY')
        decay = data.get('decay', 0)
        
        # Create and simulate alpha
        try:
            alpha_id = create_alpha(
                s=s,
                regular=expression,
                type_=instrument,
                region=region,
                universe=universe,
                delay=delay,
                neutralization=neutralization,
                decay=decay,
                name=f"AI_Mined_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            if not alpha_id:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create alpha'
                }), 500
            
            # Simulate alpha
            simulation_id = simulate_alpha(s, alpha_id)
            
            return jsonify({
                'success': True,
                'alpha_id': alpha_id,
                'simulation_id': simulation_id,
                'message': 'Alpha submitted for backtesting'
            })
        
        except Exception as e:
            logger.error(f"Error creating/simulating alpha: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to backtest: {str(e)}'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in backtest_alpha: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alpha_miner_bp.route('/api/optimize-alpha', methods=['POST'])
def optimize_alpha():
    """Optimize alpha based on backtest results"""
    try:
        data = request.json
        
        # Get original alpha and its performance
        original_expression = data.get('expression')
        performance = data.get('performance', {})
        
        # Get LLM configuration
        provider = data.get('provider', 'ollama')
        model = data.get('model', 'qwen2.5:7b')
        api_key = data.get('api_key', '')
        api_base_url = data.get('api_base_url', 'http://localhost:11434')
        
        # Build optimization prompt
        fitness = performance.get('fitness', 'N/A')
        sharpe = performance.get('sharpe', 'N/A')
        turnover = performance.get('turnover', 'N/A')
        returns = performance.get('returns', 'N/A')
        
        prompt = f"""You are an expert quantitative analyst. Analyze this alpha and suggest an optimized version.

Original Alpha: {original_expression}

Performance Metrics:
- Fitness: {fitness}
- Sharpe: {sharpe}
- Turnover: {turnover}
- Returns: {returns}

Problems identified:
{"- Low Sharpe ratio" if isinstance(sharpe, (int, float)) and sharpe < 1.5 else ""}
{"- High turnover" if isinstance(turnover, (int, float)) and turnover > 0.3 else ""}
{"- Low fitness" if isinstance(fitness, (int, float)) and fitness < 1.5 else ""}

Suggest an optimized alpha expression that addresses these issues. Consider:
1. Adding decay to reduce turnover
2. Using different time windows
3. Adding rank/normalization
4. Using group operations for stability
5. Combining multiple signals

Output ONLY the optimized alpha expression, no explanation.

Optimized expression:"""

        # Prepare API request
        if provider == 'ollama':
            api_url = f"{api_base_url.rstrip('/')}/v1/chat/completions"
            headers = {'Content-Type': 'application/json'}
        elif provider == 'deepseek':
            api_url = 'https://api.deepseek.com/chat/completions'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        elif provider == 'openai':
            api_url = f"{api_base_url.rstrip('/')}/chat/completions" if api_base_url else 'https://api.openai.com/v1/chat/completions'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        
        api_data = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 500
        }
        
        # Call AI API
        response = requests.post(api_url, headers=headers, json=api_data, timeout=180)
        
        if response.status_code == 200:
            response_data = response.json()
            optimized_expression = response_data['choices'][0]['message']['content'].strip()
            
            # Clean up the expression
            optimized_expression = optimized_expression.replace('```', '').replace('`', '').strip()
            lines = optimized_expression.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.lower().startswith('optimized'):
                    optimized_expression = line
                    break
            
            return jsonify({
                'success': True,
                'optimized_expression': optimized_expression
            })
        else:
            return jsonify({
                'success': False,
                'error': f'AI API error: {response.status_code}'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in optimize_alpha: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@alpha_miner_bp.route('/api/check-simulation', methods=['POST'])
def check_simulation():
    """Check simulation status and get results"""
    try:
        data = request.json
        alpha_id = data.get('alpha_id')
        
        if not alpha_id:
            return jsonify({
                'success': False,
                'error': 'Missing alpha_id'
            }), 400

        # Create session from config
        s = create_brain_session()
        
        # Get alpha details
        alpha_response = s.get(f'https://api.worldquantbrain.com/alphas/{alpha_id}')
        
        if alpha_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch alpha details'
            }), 500
        
        alpha_data = alpha_response.json()
        is_data = alpha_data.get('is', {})
        
        return jsonify({
            'success': True,
            'status': alpha_data.get('status'),
            'performance': {
                'fitness': is_data.get('fitness'),
                'sharpe': is_data.get('sharpe'),
                'turnover': is_data.get('turnover'),
                'returns': is_data.get('returns'),
                'margin': is_data.get('margin'),
                'longCount': is_data.get('longCount'),
                'shortCount': is_data.get('shortCount')
            }
        })
    
    except Exception as e:
        logger.error(f"Error in check_simulation: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
