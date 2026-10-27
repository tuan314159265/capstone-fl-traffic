"""Credential-free training results for the dashboard."""
def summarize(run_id, metrics, manifest, completed_at):
    clients = manifest['clients']
    sizes = {name: sum(c['sizes'][name] for c in clients)
             for name in ['train', 'validation', 'test']}
    total = sizes['train']
    tests = {c['client_id']: c for c in metrics['final_test']}
    return {
        'run_id': run_id, 'completed_at': completed_at,
        'source': metrics['data_source'], 'rounds': len(metrics['aggregation_rounds_verified']),
        'selected_round': metrics['selected_round'], 'clients': len(clients), 'sizes': sizes,
        'raw_rows': manifest['raw_rows'], 'snapshot_sha256': manifest['sha256'],
        'hist_len': manifest['history'],
        'horizons_minutes': [h*manifest['sample_minutes'] for h in manifest['horizons']],
        'test_mae_kmh': metrics['test_mae_kmh'],
        'baseline_mae_kmh': metrics['persistence_test_mae_kmh'],
        'validation_mae_kmh': metrics['selected_validation_mae_kmh'],
        'beats_baseline': metrics['test_mae_kmh'] < metrics['persistence_test_mae_kmh'],
        'live_deployed': False, 'research_result': False,
        'runtime': metrics['runtime'], 'peak_rss_mib': metrics['peak_process_rss_mib'],
        'elapsed_seconds': metrics['elapsed_seconds'],
        'nodes': [{
            'segment_key': c['segment_key'], 'train_samples': c['sizes']['train'],
            'validation_samples': c['sizes']['validation'], 'test_samples': c['sizes']['test'],
            'fedavg_weight': c['sizes']['train']/total,
            'test_mae_kmh': tests[c['client_id']]['mae_kmh'],
            'baseline_mae_kmh': tests[c['client_id']]['persistence_mae_kmh'],
        } for c in clients],
    }
