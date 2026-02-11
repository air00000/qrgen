use std::time::Instant;

/// Lightweight timing instrumentation.
///
/// Enable with `--features perf`.
/// Emits `tracing::info!` events with target="perf".
#[cfg(feature = "perf")]
pub struct PerfSpan {
    name: &'static str,
    start: Instant,
}

#[cfg(feature = "perf")]
impl PerfSpan {
    #[inline]
    pub fn new(name: &'static str) -> Self {
        Self {
            name,
            start: Instant::now(),
        }
    }
}

#[cfg(feature = "perf")]
impl Drop for PerfSpan {
    fn drop(&mut self) {
        let ms = self.start.elapsed().as_secs_f64() * 1000.0;
        tracing::info!(target: "perf", name = self.name, ms = ms);
    }
}

#[cfg(not(feature = "perf"))]
pub struct PerfSpan;

#[cfg(not(feature = "perf"))]
impl PerfSpan {
    #[inline]
    pub fn new(_name: &'static str) -> Self {
        PerfSpan
    }
}

#[macro_export]
macro_rules! perf_scope {
    ($name:expr) => {
        $crate::perf::PerfSpan::new($name)
    };
}
