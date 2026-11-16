//! Shared SMTH OS logic.
//!
//! Everything in this crate is deliberately free of platform APIs: it is the
//! single source of truth used by the Linux shell tooling, and it is written so
//! that the Android and Windows launchers can consume the same rules through
//! `smth-ahian`/`smthd` JSON instead of re-implementing them (see
//! docs/architecture/rust-migration.md).

pub mod ahian;
pub mod fsops;
pub mod ipc;
pub mod layout;
pub mod media;
pub mod palette;
pub mod settings;

/// Version of the shared logic, reported by `smthd` and used in acceptance
/// checks so a stale binary in an ISO is detectable.
pub const CORE_VERSION: &str = env!("CARGO_PKG_VERSION");

/// Deterministic, dependency-free RNG (xorshift64*).
///
/// The AHIAN script must be identical on every machine for a given seed so that
/// screenshots, tests and user reports are comparable. `rand` would work too,
/// but this keeps the ISO payload and the dependency audit small.
#[derive(Debug, Clone)]
pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Self {
        // Seed 0 is a fixed point of xorshift; never allow it.
        Self(if seed == 0 {
            0x9E37_79B9_7F4A_7C15
        } else {
            seed
        })
    }

    pub fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// Uniform integer in `low..=high` (inclusive).
    pub fn range(&mut self, low: i32, high: i32) -> i32 {
        if high <= low {
            return low;
        }
        let span = (high as i64 - low as i64 + 1) as u64;
        low + (self.next_u64() % span) as i32
    }

    /// Uniform float in `0.0..1.0`.
    pub fn unit(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }
}

#[cfg(test)]
mod tests {
    use super::Rng;

    #[test]
    fn rng_is_deterministic_and_bounded() {
        let mut a = Rng::new(7);
        let mut b = Rng::new(7);
        for _ in 0..1000 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
        let mut r = Rng::new(0);
        for _ in 0..1000 {
            let v = r.range(3, 9);
            assert!((3..=9).contains(&v), "{v} out of range");
            let u = r.unit();
            assert!((0.0..1.0).contains(&u));
        }
    }
}
