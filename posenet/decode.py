import numpy as np

from posenet.constants import *


def get_offset_point(coord, keypoint_id, offsets):
    return np.array((
        offsets[coord[0], coord[1], keypoint_id],
        offsets[coord[0], coord[1], keypoint_id + NUM_KEYPOINTS])).astype(np.int32)


def get_image_coords(heatmap_coord, keypoint_id, output_stride, offsets):
    return heatmap_coord * output_stride + get_offset_point(heatmap_coord, keypoint_id, offsets)


def traverse_to_targ_keypoint(
        edge_id, source_keypoint, target_keypoint_id, scores, offsets, output_stride, displacements
):
    height = scores.shape[0]
    width = scores.shape[1]
    num_edges = displacements.shape[2] // 2

    source_keypoint_indices = np.clip(
        np.round(source_keypoint / output_stride), a_min=0, a_max=[height - 1, width - 1]).astype(np.int32)

    displacement = np.array((
        displacements[source_keypoint_indices[0], source_keypoint_indices[1], edge_id],
        displacements[source_keypoint_indices[0], source_keypoint_indices[1], edge_id + num_edges]
    ))

    displaced_point = source_keypoint + displacement

    displaced_point_indices = np.clip(
        np.round(displaced_point / output_stride), a_min=0, a_max=[height - 1, width - 1]).astype(np.int32)

    offset_point = get_offset_point(displaced_point_indices, target_keypoint_id, offsets)

    score = scores[displaced_point_indices[0], displaced_point_indices[1], target_keypoint_id]

    position = displaced_point_indices * output_stride + offset_point

    return score, position


def decode_pose(
        root_score, root_id, root_coord,
        scores,
        offsets,
        output_stride,
        displacements_fwd,
        displacements_bwd
):
    num_parts = scores.shape[2]
    num_edges = len(PARENT_CHILD_TUPLES)

    instance_keypoint_scores = np.zeros(num_parts)
    instance_keypoint_coords = np.zeros((num_parts, 2))

    root_point = get_image_coords(root_coord, root_id, output_stride, offsets)

    instance_keypoint_scores[root_id] = root_score
    instance_keypoint_coords[root_id] = root_point

    # FIXME can we vectorize these loops cleanly?
    for edge in reversed(range(num_edges)):
        target_keypoint_id, source_keypoint_id = PARENT_CHILD_TUPLES[edge]
        if (instance_keypoint_scores[source_keypoint_id] > 0.0 and
                instance_keypoint_scores[target_keypoint_id] == 0.0):
            score, coords = traverse_to_targ_keypoint(
                edge,
                instance_keypoint_coords[source_keypoint_id],
                target_keypoint_id,
                scores, offsets, output_stride, displacements_bwd)
            instance_keypoint_scores[target_keypoint_id] = score
            instance_keypoint_coords[target_keypoint_id] = coords

    for edge in range(num_edges):
        source_keypoint_id, target_keypoint_id = PARENT_CHILD_TUPLES[edge]
        if (instance_keypoint_scores[source_keypoint_id] > 0.0 and
                instance_keypoint_scores[target_keypoint_id] == 0.0):
            score, coords = traverse_to_targ_keypoint(
                edge,
                instance_keypoint_coords[source_keypoint_id],
                target_keypoint_id,
                scores, offsets, output_stride, displacements_fwd)
            instance_keypoint_scores[target_keypoint_id] = score
            instance_keypoint_coords[target_keypoint_id] = coords

    return instance_keypoint_scores, instance_keypoint_coords