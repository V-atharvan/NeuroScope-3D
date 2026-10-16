/**
 * NeuroScope 3D - Spatial Coordinate & Affine Utilities
 * ======================================================
 * Mathematically rigorous coordinate conversions between discrete voxel grid [i, j, k]
 * and continuous physical world millimetre [x, y, z] (RAS/LPS space) using NIfTI 4x4 spatial affines.
 */

/**
 * Inverts a 4x4 affine transformation matrix.
 * @param {number[][]} m - 4x4 matrix
 * @returns {number[][]} inverse 4x4 matrix
 */
export function matrixInverse4x4(m) {
  const inv = Array.from({ length: 4 }, () => new Array(4).fill(0));

  const a00 = m[0][0], a01 = m[0][1], a02 = m[0][2], a03 = m[0][3];
  const a10 = m[1][0], a11 = m[1][1], a12 = m[1][2], a13 = m[1][3];
  const a20 = m[2][0], a21 = m[2][1], a22 = m[2][2], a23 = m[2][3];
  const a30 = m[3][0], a31 = m[3][1], a32 = m[3][2], a33 = m[3][3];

  const b00 = a00 * a11 - a01 * a10;
  const b01 = a00 * a12 - a02 * a10;
  const b02 = a00 * a13 - a03 * a10;
  const b03 = a01 * a12 - a02 * a11;
  const b04 = a01 * a13 - a03 * a11;
  const b05 = a02 * a13 - a03 * a12;
  const b06 = a20 * a31 - a21 * a30;
  const b07 = a20 * a32 - a22 * a30;
  const b08 = a20 * a33 - a23 * a30;
  const b09 = a21 * a32 - a22 * a31;
  const b10 = a21 * a33 - a23 * a31;
  const b11 = a22 * a33 - a23 * a32;

  let det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
  if (Math.abs(det) < 1e-12) {
    throw new Error('Singular affine matrix cannot be inverted');
  }
  const invDet = 1.0 / det;

  inv[0][0] = (a11 * b11 - a12 * b10 + a13 * b09) * invDet;
  inv[0][1] = (-a01 * b11 + a02 * b10 - a03 * b09) * invDet;
  inv[0][2] = (a31 * b05 - a32 * b04 + a33 * b03) * invDet;
  inv[0][3] = (-a21 * b05 + a22 * b04 - a23 * b03) * invDet;

  inv[1][0] = (-a10 * b11 + a12 * b08 - a13 * b07) * invDet;
  inv[1][1] = (a00 * b11 - a02 * b08 + a03 * b07) * invDet;
  inv[1][2] = (-a30 * b05 + a32 * b02 - a33 * b01) * invDet;
  inv[1][3] = (a20 * b05 - a22 * b02 + a23 * b01) * invDet;

  inv[2][0] = (a10 * b10 - a11 * b08 + a13 * b06) * invDet;
  inv[2][1] = (-a00 * b10 + a01 * b08 - a03 * b06) * invDet;
  inv[2][2] = (a30 * b04 - a31 * b02 + a33 * b00) * invDet;
  inv[2][3] = (-a20 * b04 + a21 * b02 - a23 * b00) * invDet;

  inv[3][0] = (-a10 * b09 + a11 * b07 - a12 * b06) * invDet;
  inv[3][1] = (a00 * b09 - a01 * b07 + a02 * b06) * invDet;
  inv[3][2] = (-a30 * b03 + a31 * b01 - a32 * b00) * invDet;
  inv[3][3] = (a20 * b03 - a21 * b01 + a22 * b00) * invDet;

  return inv;
}

/**
 * Transforms voxel coordinates [i, j, k] to continuous physical world millimetres [x, y, z].
 * [x, y, z, 1]^T = Affine * [i, j, k, 1]^T
 * @param {[number, number, number]} voxel - [i, j, k] discrete voxel coordinates
 * @param {number[][]} affine - 4x4 NIfTI affine matrix
 * @returns {[number, number, number]} [x, y, z] in mm
 */
export function voxelToWorld(voxel, affine) {
  if (!voxel || voxel.length < 3) return [0, 0, 0];
  if (!affine || affine.length < 4 || affine[0].length < 4) {
    return [voxel[0], voxel[1], voxel[2]];
  }

  const i = voxel[0];
  const j = voxel[1];
  const k = voxel[2];

  const x = affine[0][0] * i + affine[0][1] * j + affine[0][2] * k + affine[0][3];
  const y = affine[1][0] * i + affine[1][1] * j + affine[1][2] * k + affine[1][3];
  const z = affine[2][0] * i + affine[2][1] * j + affine[2][2] * k + affine[2][3];

  return [Number(x.toFixed(2)), Number(y.toFixed(2)), Number(z.toFixed(2))];
}

/**
 * Transforms continuous physical world coordinates [x, y, z] in mm to discrete voxel index [i, j, k].
 * [i, j, k, 1]^T = Affine^-1 * [x, y, z, 1]^T
 * @param {[number, number, number]} world - [x, y, z] in mm
 * @param {number[][]} affine - 4x4 NIfTI affine matrix
 * @param {[number, number, number]} [bounds] - optional volume dimensions [dimX, dimY, dimZ] to clamp
 * @returns {[number, number, number]} [i, j, k] discrete voxel indices
 */
export function worldToVoxel(world, affine, bounds = null) {
  if (!world || world.length < 3) return [0, 0, 0];
  if (!affine || affine.length < 4 || affine[0].length < 4) {
    return [Math.round(world[0]), Math.round(world[1]), Math.round(world[2])];
  }

  const inv = matrixInverse4x4(affine);
  const x = world[0];
  const y = world[1];
  const z = world[2];

  let i = Math.round(inv[0][0] * x + inv[0][1] * y + inv[0][2] * z + inv[0][3]);
  let j = Math.round(inv[1][0] * x + inv[1][1] * y + inv[1][2] * z + inv[1][3]);
  let k = Math.round(inv[2][0] * x + inv[2][1] * y + inv[2][2] * z + inv[2][3]);

  if (bounds && bounds.length >= 3) {
    i = Math.max(0, Math.min(bounds[0] - 1, i));
    j = Math.max(0, Math.min(bounds[1] - 1, j));
    k = Math.max(0, Math.min(bounds[2] - 1, k));
  }

  return [i, j, k];
}

/**
 * Computes voxel spacing along each spatial dimension from affine columns.
 * @param {number[][]} affine - 4x4 matrix
 * @returns {[number, number, number]} [sx, sy, sz] in mm
 */
export function computeVoxelSpacing(affine) {
  if (!affine || affine.length < 3 || affine[0].length < 3) {
    return [1.0, 1.0, 1.0];
  }
  const sx = Math.sqrt(affine[0][0] ** 2 + affine[1][0] ** 2 + affine[2][0] ** 2);
  const sy = Math.sqrt(affine[0][1] ** 2 + affine[1][1] ** 2 + affine[2][1] ** 2);
  const sz = Math.sqrt(affine[0][2] ** 2 + affine[1][2] ** 2 + affine[2][2] ** 2);
  return [Number(sx.toFixed(3)), Number(sy.toFixed(3)), Number(sz.toFixed(3))];
}

/**
 * Computes single voxel volume in mm³ and mL using the determinant of the 3x3 rotation/scale submatrix.
 * @param {number[][]} affine - 4x4 matrix
 * @returns {{ mm3: number, ml: number }}
 */
export function computeVoxelVolume(affine) {
  if (!affine || affine.length < 3 || affine[0].length < 3) {
    return { mm3: 1.0, ml: 0.001 };
  }
  const m00 = affine[0][0], m01 = affine[0][1], m02 = affine[0][2];
  const m10 = affine[1][0], m11 = affine[1][1], m12 = affine[1][2];
  const m20 = affine[2][0], m21 = affine[2][1], m22 = affine[2][2];

  const det = m00 * (m11 * m22 - m12 * m21) -
              m01 * (m10 * m22 - m12 * m20) +
              m02 * (m10 * m21 - m11 * m20);

  const mm3 = Math.abs(det);
  const ml = mm3 / 1000.0;
  return { mm3: Number(mm3.toFixed(3)), ml: Number(ml.toFixed(6)) };
}

/**
 * Infers 3-letter anatomical orientation code (e.g. 'RAS', 'LPS') from affine direction cosines.
 * @param {number[][]} affine - 4x4 matrix
 * @returns {string} 3-letter orientation string
 */
export function getAnatomicalOrientation(affine) {
  if (!affine || affine.length < 3 || affine[0].length < 3) return 'RAS';

  const labels = [['R', 'L'], ['A', 'P'], ['S', 'I']];
  let orientation = '';

  for (let c = 0; c < 3; c++) {
    let maxVal = -1;
    let maxIdx = 0;
    let isPos = true;

    for (let r = 0; r < 3; r++) {
      const val = affine[r][c];
      if (Math.abs(val) > maxVal) {
        maxVal = Math.abs(val);
        maxIdx = r;
        isPos = val >= 0;
      }
    }
    orientation += isPos ? labels[maxIdx][0] : labels[maxIdx][1];
  }

  return orientation;
}
