use std::collections::HashSet;

fn split_list(input: &str) -> impl Iterator<Item = String> + '_ {
    input
        .split(|ch: char| matches!(ch, ',' | '\n' | '\r' | '\t' | ';'))
        .map(str::trim)
        .filter(|item| !item.is_empty())
        .map(|item| item.to_uppercase())
}

pub fn split_symbols(input: &str) -> Vec<String> {
    let mut seen = HashSet::new();
    split_list(input)
        .filter(|item| seen.insert(item.clone()))
        .collect()
}

pub fn parse_optional_allocations(
    input: &str,
    expected_count: usize,
) -> Result<Option<Vec<f64>>, String> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }

    let values = trimmed
        .split(|ch: char| matches!(ch, ',' | '\n' | '\r' | '\t' | ';'))
        .map(str::trim)
        .filter(|item| !item.is_empty())
        .map(|item| {
            item.parse::<f64>()
                .map_err(|_| format!("Invalid allocation value: {item}"))
        })
        .collect::<Result<Vec<_>, _>>()?;

    if values.len() != expected_count {
        return Err(format!(
            "Allocation count ({}) must match fund count ({}).",
            values.len(),
            expected_count
        ));
    }

    Ok(Some(values))
}
