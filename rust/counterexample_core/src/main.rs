use counterexample_core::search_strong_variant_false_small_n;

fn main() {
    let result = search_strong_variant_false_small_n(12);
    if result.found {
        println!("counterexample_found=true witness={:?}", result.witness);
    } else {
        println!("counterexample_found=false checked_bound={}", result.checked_bound);
    }
}
