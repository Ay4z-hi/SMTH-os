//! Window geometry: cascading placement, edge snapping and split-screen.
//!
//! The Linux shell uses these rules through `smthd`; tests pin the invariants
//! that the Python shell previously implemented ad-hoc (or not at all).

use serde::{Deserialize, Serialize};

/// Minimum usable window size. Smaller screens get a clamped, still-visible
/// window instead of an off-screen one.
pub const MIN_W: u32 = 320;
pub const MIN_H: u32 = 200;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub w: u32,
    pub h: u32,
}

impl Rect {
    pub fn new(x: i32, y: i32, w: u32, h: u32) -> Rect {
        Rect { x, y, w, h }
    }

    pub fn right(&self) -> i32 {
        self.x + self.w as i32
    }

    pub fn bottom(&self) -> i32 {
        self.y + self.h as i32
    }

    pub fn area(&self) -> u64 {
        self.w as u64 * self.h as u64
    }

    /// True when `other` is fully inside `self`.
    pub fn contains(&self, other: &Rect) -> bool {
        other.x >= self.x
            && other.y >= self.y
            && other.right() <= self.right()
            && other.bottom() <= self.bottom()
    }

    pub fn overlaps(&self, other: &Rect) -> bool {
        self.x < other.right()
            && other.x < self.right()
            && self.y < other.bottom()
            && other.y < self.bottom()
    }

    pub fn intersect(&self, other: &Rect) -> Option<Rect> {
        let x = self.x.max(other.x);
        let y = self.y.max(other.y);
        let r = self.right().min(other.right());
        let b = self.bottom().min(other.bottom());
        if r <= x || b <= y {
            None
        } else {
            Some(Rect::new(x, y, (r - x) as u32, (b - y) as u32))
        }
    }

    /// Shrink by `dx`/`dy` on every side, never past `MIN_W`/`MIN_H`.
    pub fn inset(&self, dx: i32, dy: i32) -> Rect {
        let w = (self.w as i32 - 2 * dx).max(MIN_W as i32) as u32;
        let h = (self.h as i32 - 2 * dy).max(MIN_H as i32) as u32;
        Rect::new(self.x + dx, self.y + dy, w, h)
    }

    /// Keep `self` inside `work`, shrinking only when it is larger.
    pub fn clamped_into(&self, work: &Rect) -> Rect {
        let w = self.w.min(work.w).max(MIN_W.min(work.w));
        let h = self.h.min(work.h).max(MIN_H.min(work.h));
        let max_x = work.right() - w as i32;
        let max_y = work.bottom() - h as i32;
        Rect::new(
            self.x.clamp(work.x, max_x.max(work.x)),
            self.y.clamp(work.y, max_y.max(work.y)),
            w,
            h,
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Snap {
    Left,
    Right,
    Top,
    Bottom,
    Maximize,
    Center,
}

/// A work area plus the inter-window gap used by split-screen layouts.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Layout {
    pub work: Rect,
    pub gap: u32,
}

impl Layout {
    pub fn new(work: Rect, gap: u32) -> Layout {
        Layout { work, gap }
    }

    /// Half-screen snap. `Left`/`Right` split columns, `Top`/`Bottom` rows.
    pub fn snap(&self, snap: Snap) -> Rect {
        let g = self.gap as i32;
        let w = self.work;
        let half_w = ((w.w as i32 - g) / 2).max(MIN_W as i32) as u32;
        let half_h = ((w.h as i32 - g) / 2).max(MIN_H as i32) as u32;
        match snap {
            Snap::Left => Rect::new(w.x, w.y, half_w, w.h),
            Snap::Right => Rect::new(w.right() - half_w as i32, w.y, half_w, w.h),
            Snap::Top => Rect::new(w.x, w.y, w.w, half_h),
            Snap::Bottom => Rect::new(w.x, w.bottom() - half_h as i32, w.w, half_h),
            Snap::Maximize => w,
            Snap::Center => {
                let cw = ((w.w as f64 * 0.62) as u32).max(MIN_W);
                let ch = ((w.h as f64 * 0.72) as u32).max(MIN_H);
                Rect::new(
                    w.x + (w.w as i32 - cw as i32) / 2,
                    w.y + (w.h as i32 - ch as i32) / 2,
                    cw,
                    ch,
                )
                .clamped_into(&w)
            }
        }
    }

    /// `panes`-way vertical split, `index` starting at 0. Panes tile the work
    /// area exactly (gap included between neighbours, not at the edges).
    pub fn split(&self, panes: u8, index: u8) -> Rect {
        let panes = panes.max(1);
        let index = index.min(panes - 1) as i32;
        let n = panes as i32;
        let total_gap = self.gap as i32 * (n - 1);
        let usable = (self.work.w as i32 - total_gap).max(n * MIN_W as i32);
        let base = usable / n;
        // Distribute the rounding remainder so the panes still tile exactly.
        let extra = usable % n;
        let x_off: i32 =
            (0..index).map(|i| base + i32::from(i < extra)).sum::<i32>() + index * self.gap as i32;
        let width = base + i32::from(index < extra);
        Rect::new(
            self.work.x + x_off,
            self.work.y,
            width.max(1) as u32,
            self.work.h,
        )
    }

    /// How many distinct cascade positions exist for this work area. Used by
    /// the shell to keep placement predictable and by the tests to verify that
    /// placement wraps instead of drifting off-screen.
    pub fn cascade_slots(&self) -> usize {
        let step = (self.gap as i32 * 8).clamp(24, 48);
        ((self.work.w as i32 - MIN_W as i32) / step)
            .min((self.work.h as i32 - MIN_H as i32) / step)
            .max(1) as usize
    }

    /// Cascading default placement: each new window steps down/right and wraps
    /// instead of stacking exactly on top of the previous one.
    pub fn cascade(&self, size: (u32, u32), index: usize) -> Rect {
        let step = (self.gap as i32 * 8).clamp(24, 48);
        let slots = self.cascade_slots();
        let i = (index % slots) as i32;
        let start = self.work.inset(step * 2, step * 2);
        Rect::new(start.x + i * step, start.y + i * step, size.0, size.1).clamped_into(&self.work)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn screen() -> Layout {
        Layout::new(Rect::new(0, 0, 1920, 1080), 8)
    }

    #[test]
    fn snap_halves_tile_the_screen() {
        let l = screen();
        let left = l.snap(Snap::Left);
        let right = l.snap(Snap::Right);
        assert!(l.work.contains(&left));
        assert!(l.work.contains(&right));
        assert!(!left.overlaps(&right), "halves must not overlap");
        assert_eq!(left.w + right.w + l.gap, l.work.w);
        assert_eq!(right.right(), l.work.right());
        let top = l.snap(Snap::Top);
        let bottom = l.snap(Snap::Bottom);
        assert!(!top.overlaps(&bottom));
        assert_eq!(top.h + bottom.h + l.gap, l.work.h);
        assert_eq!(bottom.bottom(), l.work.bottom());
    }

    #[test]
    fn maximize_and_center_stay_inside() {
        let l = screen();
        assert_eq!(l.snap(Snap::Maximize), l.work);
        let c = l.snap(Snap::Center);
        assert!(l.work.contains(&c));
        assert!(c.w > 0 && c.h > 0);
    }

    #[test]
    fn split_tiles_exactly_for_any_pane_count() {
        let l = screen();
        for panes in 1u8..=4 {
            let mut covered = 0i64;
            let mut prev: Option<Rect> = None;
            let mut rects = Vec::new();
            for i in 0..panes {
                let r = l.split(panes, i);
                assert!(
                    l.work.contains(&r),
                    "pane {i}/{panes} escapes work area: {r:?}"
                );
                if let Some(p) = prev {
                    assert!(p.right() <= r.x, "panes overlap: {p:?} and {r:?}");
                    assert_eq!(r.x - p.right(), l.gap as i32);
                }
                covered += r.w as i64;
                prev = Some(r);
                rects.push(r);
            }
            covered += l.gap as i64 * (panes as i64 - 1);
            assert_eq!(
                covered as u32, l.work.w,
                "panes {panes} do not tile the width"
            );
            assert_eq!(rects.last().unwrap().right(), l.work.right());
        }
    }

    #[test]
    fn split_clamps_out_of_range_index() {
        let l = screen();
        assert_eq!(l.split(2, 9), l.split(2, 1));
        assert_eq!(l.split(0, 0), l.split(1, 0));
    }

    #[test]
    fn cascade_steps_and_wraps_without_leaving_screen() {
        let l = screen();
        let first = l.cascade((900, 600), 0);
        let second = l.cascade((900, 600), 1);
        assert!(
            second.x > first.x && second.y > first.y,
            "cascade must offset"
        );
        assert!(l.work.contains(&first));
        for i in 0..50 {
            assert!(l.work.contains(&l.cascade((1200, 900), i)));
        }
        // Wrapping must repeat the first position rather than drift away.
        let slots = l.cascade_slots();
        assert!(slots > 1);
        let a = l.cascade((400, 300), 0);
        let b = l.cascade((400, 300), slots);
        assert_eq!(a, b);
        assert_eq!(
            l.cascade((400, 300), slots * 3 + 1),
            l.cascade((400, 300), 1)
        );
        // Every slot is on-screen, and consecutive slots differ.
        for i in 0..slots {
            assert!(l.work.contains(&l.cascade((400, 300), i)));
        }
        assert_ne!(l.cascade((400, 300), 0), l.cascade((400, 300), 1));
    }

    #[test]
    fn cascade_shrinks_oversized_windows_onto_the_screen() {
        let small = Layout::new(Rect::new(0, 0, 1024, 768), 8);
        let r = small.cascade((4000, 3000), 3);
        assert!(small.work.contains(&r));
        assert_eq!(r.w, 1024);
        assert_eq!(r.h, 768);
    }

    #[test]
    fn rect_helpers() {
        let a = Rect::new(10, 10, 100, 100);
        let b = Rect::new(50, 50, 100, 100);
        assert!(a.overlaps(&b));
        assert!(!a.contains(&b));
        assert_eq!(a.intersect(&b), Some(Rect::new(50, 50, 60, 60)));
        assert_eq!(a.intersect(&Rect::new(500, 500, 10, 10)), None);
        assert_eq!(a.right(), 110);
        assert_eq!(a.area(), 10_000);
        assert_eq!(a.inset(150, 150).w, MIN_W);
    }
}
