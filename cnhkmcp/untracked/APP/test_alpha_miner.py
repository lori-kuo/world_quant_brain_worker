"""
测试 alpha_miner 模块的功能
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blueprints.alpha_miner import load_user_config_credentials, create_brain_session

def test_config():
    """测试配置读取"""
    print("=" * 50)
    print("测试1: 读取用户配置")
    print("=" * 50)
    
    email, password = load_user_config_credentials()
    
    if email and password:
        print(f"✓ 成功读取配置")
        print(f"  Email: {email}")
        print(f"  Password: {'*' * len(password)}")
        return True
    else:
        print("✗ 配置读取失败")
        return False

def test_authentication():
    """测试认证"""
    print("\n" + "=" * 50)
    print("测试2: BRAIN API 认证")
    print("=" * 50)
    
    try:
        session = create_brain_session()
        print(f"✓ 认证成功")
        print(f"  Session对象: {session}")
        return session
    except Exception as e:
        print(f"✗ 认证失败: {e}")
        return None

def test_get_datasets(session):
    """测试获取datasets"""
    print("\n" + "=" * 50)
    print("测试3: 获取 Datasets")
    print("=" * 50)
    
    if not session:
        print("✗ 没有有效的session，跳过测试")
        return False
    
    try:
        response = session.get('https://api.worldquantbrain.com/data-sets', params={'limit': 5})
        print(f"  HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            datasets = data.get('results', [])
            print(f"✓ 成功获取数据")
            print(f"  数据集数量: {len(datasets)}")
            
            if datasets:
                print(f"\n  前3个数据集:")
                for i, ds in enumerate(datasets[:3], 1):
                    print(f"    {i}. {ds.get('name', 'Unknown')}")
                    print(f"       ID: {ds.get('id', 'N/A')}")
            
            return True
        else:
            print(f"✗ API返回错误: {response.status_code}")
            print(f"  响应内容: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_get_user_profile(session):
    """测试获取用户信息"""
    print("\n" + "=" * 50)
    print("测试4: 获取用户信息")
    print("=" * 50)
    
    if not session:
        print("✗ 没有有效的session，跳过测试")
        return False
    
    try:
        response = session.get('https://api.worldquantbrain.com/users/self')
        print(f"  HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            user = response.json()
            print(f"✓ 成功获取用户信息")
            print(f"  用户名: {user.get('username', 'N/A')}")
            print(f"  邮箱: {user.get('email', 'N/A')}")
            return True
        else:
            print(f"✗ API返回错误: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("Alpha Miner 模块测试")
    print("=" * 50 + "\n")
    
    # 测试1: 配置读取
    if not test_config():
        print("\n❌ 配置读取失败，终止测试")
        return
    
    # 测试2: 认证
    session = test_authentication()
    if not session:
        print("\n❌ 认证失败，终止测试")
        return
    
    # 测试3: 获取datasets
    test_get_datasets(session)
    
    # 测试4: 获取用户信息
    test_get_user_profile(session)
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == '__main__':
    main()
