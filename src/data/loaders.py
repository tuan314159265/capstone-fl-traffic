"""Explicit dataset dispatch; real runs never fall back to synthetic data."""
def client_loaders(config, client_id, round_id=0):
    if config['dataset']['name'] == 'tomtom-snapshot':
        from src.data.traffic import client_loaders as load
    elif config['dataset']['name'] == 'synthetic-traffic-smoke':
        from src.data.synthetic import client_loaders as load
    else:
        raise ValueError('Unsupported dataset')
    return load(config, client_id, round_id)
