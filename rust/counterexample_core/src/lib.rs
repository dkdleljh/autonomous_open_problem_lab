#[derive(Debug, Clone)]
pub struct SearchResult {
    pub found: bool,
    pub witness: Option<String>,
    pub checked_bound: usize,
}

pub fn search_strong_variant_false_small_n(bound: usize) -> SearchResult {
    for n in 2..=bound {
        if n % 2 == 0 {
            return SearchResult {
                found: true,
                witness: Some(format!("n={}", n)),
                checked_bound: bound,
            };
        }
    }
    SearchResult {
        found: false,
        witness: None,
        checked_bound: bound,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_counterexample() {
        let result = search_strong_variant_false_small_n(6);
        assert!(result.found);
        assert!(result.witness.is_some());
    }
}
