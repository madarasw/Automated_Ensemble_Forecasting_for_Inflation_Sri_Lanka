"""GPU detection and provenance.

Every experiment script calls require_cuda() before any AutoGluon fit. Hardware is a
frozen decision (local GPU, no silent CPU fallback) - this module is the single place
that enforces it, so no per-script code can accidentally skip the check.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class GPUInfo:
    name: str
    vram_gb: float
    driver_version: str
    cuda_runtime: str

    def as_dict(self) -> dict:
        return {
            "gpu_name": self.name,
            "gpu_vram_gb": round(self.vram_gb, 2),
            "gpu_driver_version": self.driver_version,
            "cuda_runtime": self.cuda_runtime,
        }


def require_cuda() -> GPUInfo:
    """Fail loudly if CUDA is unavailable. Returns GPU provenance for run_config.json.

    Deliberately imports torch inside the function: this module can be imported by
    code that doesn't need torch (e.g. the Excel plan surgery script) without forcing
    the heavy import.
    """
    import torch

    if not torch.cuda.is_available():
        cuda_build = torch.version.cuda
        raise RuntimeError(
            "CUDA is not available to this process (torch.cuda.is_available() is False, "
            f"torch built with cuda={cuda_build!r}). Hardware is a frozen decision: local GPU, "
            "no silent CPU fallback. Fix the torch install (see Data/methodology... or "
            "reinstall a CUDA-tagged torch wheel matching the driver's CUDA version) "
            "before running any experiment."
        )

    # torch.cuda.is_available() can be True while actual kernel execution still fails -
    # discovered firsthand on this machine: a cu126 build reported is_available()=True
    # for an RTX 5050 (compute capability sm_120, Blackwell) but had no compiled kernels
    # for that CC and would have failed or silently misbehaved on the first real op. The
    # only reliable check is running one.
    try:
        _probe = torch.matmul(torch.randn(64, 64, device="cuda"), torch.randn(64, 64, device="cuda"))
        _probe.sum().item()  # forces synchronization, surfaces a kernel error now, not mid-fit
    except Exception as exc:
        raise RuntimeError(
            "torch.cuda.is_available() is True, but a real CUDA matmul on this device failed "
            f"({type(exc).__name__}: {exc}). This usually means the installed torch build has "
            "no compiled kernels for this GPU's compute capability - check `python -c "
            "\"import torch; torch.randn(1,device='cuda')\"` output for the suggested CUDA "
            "index (e.g. cu129/cu130/cu132) and reinstall torch from that index. Hardware is a "
            "frozen decision: local GPU, no silent CPU fallback - this must be fixed, not caught "
            "and ignored."
        ) from exc

    name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    cuda_runtime = torch.version.cuda or "unknown"
    driver_version = _nvidia_smi_driver_version()
    return GPUInfo(name=name, vram_gb=vram_gb, driver_version=driver_version, cuda_runtime=cuda_runtime)


def _nvidia_smi_driver_version() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return out.stdout.strip().splitlines()[0]
    except Exception:
        return "unknown (nvidia-smi query failed)"


if __name__ == "__main__":
    info = require_cuda()
    print(f"GPU: {info.name}")
    print(f"VRAM: {info.vram_gb:.2f} GB")
    print(f"Driver: {info.driver_version}")
    print(f"CUDA runtime (torch build): {info.cuda_runtime}")
