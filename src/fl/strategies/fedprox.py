"""FedProx local objective; server still uses sample-weighted averaging."""
def proximal_penalty(parameters, reference, mu):
    if mu < 0:raise ValueError('FedProx mu must be nonnegative')
    return .5*mu*sum((parameter-anchor).square().sum() for parameter,anchor in zip(parameters,reference))
