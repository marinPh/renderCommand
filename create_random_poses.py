"""
Author:     Tim Vaughan-Whitehead
Date:       June 9, 2023
Description: Generates random poses for a single object.
"""

import numpy as np
import os
import math
from pyquaternion import Quaternion
import re

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random as rand
from Utils.save_info_to_files_utils import save_camera_info_to_file
import Utils.dataset_constants as dc

################################################
# User-defined inputs
#get object_id and pose_id from command line
pose_id = int(sys.argv[-1])
object_name = sys.argv[-2]


# Output directory

# Number of poses to generate
num_poses : int = dc.val_num_poses

# ID of the object to be rendered
object_id : str = object_name.split("_")[0]

# Whether the sun orientation is randomly generated or not
sun_rnd_generated : bool = True
output_directory : str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"input", f"{object_id}_0{pose_id}")


################################################
# Object properties

#bbox of current object
def extract_corners(file_path):
    with open(file_path, 'r') as file:
        content = file.read()

    # Regular expressions to extract relevant information
    min_corner_pattern = re.compile(r"Min corner \(x, y, z\): \[([-0-9.]+), ([-0-9.]+), ([-0-9.]+)\]")
    max_corner_pattern = re.compile(r"Max corner \(x, y, z\): \[([-0-9.]+), ([-0-9.]+), ([-0-9.]+)\]")

    # Find matches using regular expressions
    min_corner_match = min_corner_pattern.search(content)
    max_corner_match = max_corner_pattern.search(content)

    if min_corner_match and max_corner_match:
        # Extract values from the matches
        min_corner_values = [float(min_corner_match.group(i)) for i in range(1, 4)]
        max_corner_values = [float(max_corner_match.group(i)) for i in range(1, 4)]

        return min_corner_values, max_corner_values
    else:
        raise ValueError("Could not find min and max corners in the file.")
        
#size of current object
mincorner,maxcorner = extract_corners(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"objects","inertia", f"{object_name}_info.txt"))
size = np.abs(np.array(maxcorner) - np.array(mincorner))

output_directory = (
    output_directory
)

#min and max object-camera distance, based on  the size of the object

def calculate_distance_with_fov(object_size, fov_degrees, image_dimension, coverage_ratio):
    """
    Calculates the distance from the camera to the object based on the desired coverage ratio of the image,
    assuming a typical camera field of view.
    """
    fov_radians = math.radians(fov_degrees)
    max_object_dimension = max(object_size)
    covered_image_dimension = coverage_ratio * image_dimension
    distance = (max_object_dimension / 2) / math.tan(fov_radians / 2)
    adjusted_distance = distance * (image_dimension / covered_image_dimension)
    return adjusted_distance

#min object-camera distance
min_distance = calculate_distance_with_fov(size, dc.camera_fov, 1024, 0.25 ** 0.5)

#max object-camera distance
max_distance = calculate_distance_with_fov(size, dc.camera_fov, 1024, 0.15 ** 0.5)

def generate_random_poses(num_poses, object_id, output_directory, sun_rnd_generated, num_frustums, min_distance, max_distance, fov, camera_position, camera_direction, scene_info_file_name, sun_orientations_file_name, scene_gt_file_name, camera_info_file_name):
    """
    Generate a given number of random poses of a given object
    """
    positions, rotations = generate_non_uniform_poses(num_frustums, num_poses, max_distance, min_distance, fov, camera_position)

    # Create the output directory if it doesn't exist yet
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if sun_rnd_generated:
        sun_orientations = generate_random_sun_orientations(num_poses)
        sun_orientations = np.array(sun_orientations)
        save_sun_orientations_to_file(sun_orientations, output_directory, sun_orientations_file_name)
        
    # Save the camera info to a text file in the specified directory
    save_camera_info_to_file(output_directory)

    # Save the scene ground truth data to a text file in the specified directory
    save_vals_to_file(output_directory, scene_gt_file_name, positions, rotations, object_id)

    # Save the initial inputs to a separate file
    save_rnd_gen_gt_info_to_file(output_directory, object_id, num_poses, sun_rnd_generated, min_distance, max_distance, dc.nb_layers, dc.light_energy, dc.sun_orientations_file_name, dc.scene_info_file_name, dc.random_poses_motion_id)

    
def generate_non_uniform_poses(num_frustums : int, num_points : int, max_dist : float, min_dist : float, 
                                fov : int, origin : np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    This function generates non-uniform points with uneven density in a pyramid-shaped volume with
    specified parameters. The points are generated in a way that the density of points is higher
    closer to the origin of the frustum and lower further away from the origin.
    
    Returns a tuple containing two numpy arrays:
    `positions` and `rotations`.
    """
    
    # Generate points with uneven density
    num_points_per_frustum, remainder_points = divmod(num_points, num_frustums)
    positions = []
    rotations = []
    curr_dist = min_dist

    for i in range(num_frustums):
        curr_dist = min_dist + (i + 1) * (max_dist- min_dist) / num_frustums
        # Add an extra point to the first remainder_points frustums
        num_points = num_points_per_frustum + (i < remainder_points)
        section_points = generate_points_in_frustum(num_points, curr_dist, min_dist, fov, origin)
        positions.extend(section_points)
        rotations.extend([Quaternion.random().elements for _ in range(num_points)])

    positions = np.array(positions)
    rotations = np.array(rotations)
    
    return positions, rotations

def generate_points_in_frustum(num_points : int, max_dist : float, min_dist : float, fov : int, origin : np.ndarray) -> np.ndarray:
    half_base_angle = np.deg2rad(fov / 2)
    half_base_size = max_dist * np.tan(half_base_angle)

    inside_points = []
    num_generated_points = 0

    while len(inside_points) < num_points:
        
        z = rand.uniform(min_distance,max_distance)
        x = rand.uniform((-1)*(math.sin(math.radians(fov/2)))*z,(math.sin(math.radians(fov/2)))*z)
        y = rand.uniform((-1)*(math.sin(math.radians(fov/2)))*z,(math.sin(math.radians(fov/2)))*z)
        point = np.array([x + origin[0], y + origin[1], z + origin[2]])
        
        # Check if the point is inside the frustum
        inside_points.append(point)
        num_generated_points += 1
            
    return np.array(inside_points)

def generate_random_sun_orientations(num_orientations: int):
    phi = 2 * np.pi * np.random.rand(num_orientations)  # azimuthal angle
    theta = np.arccos(2 * np.random.rand(num_orientations) - 1)  # polar angle

    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    z = np.cos(theta)
    
    return np.column_stack([x, y, z])


def save_rnd_gen_gt_info_to_file(output_directory : str, group_id: str, num_poses : int,
                                 sun_rnd_generated : bool,
                                 min_distance : float, 
                                 max_distance : float, 
                                 num_frustums : int = dc.nb_layers,  
                                 sun_energy : float = dc.light_energy, 
                                 sun_dirs_file : str = dc.sun_orientations_file_name, 
                                 scene_info_file_name : str = dc.scene_info_file_name, 
                                 rnd_gen_mt_id : str = dc.random_poses_motion_id) -> None:
    
    with open(os.path.join(output_directory, scene_info_file_name), 'w') as f:
        f.write(f"----- Random poses info (ID : {rnd_gen_mt_id}) -----\n\n")
        
        f.write(f"Object Group ID: {group_id}\n")
        
        f.write(f"\n--- Pose generation info ---\n")
        f.write(f"Min distance (from camera): {min_distance} meters\n")
        f.write(f"Max distance (from camera): {max_distance} meters\n")
        f.write(f"Number of poses: {num_poses}\n")
        f.write(f"Number of generated layers: {num_frustums}\n")
        
        f.write(f"\n--- Lighting info ---\n")
        if sun_rnd_generated:
            f.write(f"Sun orientation : Random orientation for each pose ({sun_dirs_file})\n")
        else:
            f.write(f"Sun orientation [x, y, z] (unit vector): \n")
        f.write(f"Sun energy : {sun_energy} W/m^2\n")

def save_sun_orientations_to_file(sun_orientations : np.ndarray, output_directory : str, sun_orientations_file_name : str):
    with open(os.path.join(output_directory, sun_orientations_file_name), 'w') as f:
        for i, orientation in enumerate(sun_orientations):
            f.write(f"{i:05d},{orientation[0]:.6f},{orientation[1]:.6f},{orientation[2]:.6f}\n")

def save_vals_to_file(output_directory : str, output_file : str, positions : np.ndarray, orientations : np.ndarray, object_id : str):
    # Save the output array to a text file in the specified directory with the desired delimiter and format
    with open(os.path.join(output_directory, output_file), 'w') as f:
        for i, (orientation, position) in enumerate(zip(orientations, positions)):
            f.write(f"{i:05d},{object_id},{orientation[0]:.6f},{orientation[1]:.6f},{orientation[2]:.6f},{orientation[3]:.6f},{position[0]:.6f},{position[1]:.6f},{position[2]:.6f}\n")


def main():

    generate_random_poses(num_poses, object_id, output_directory, sun_rnd_generated, dc.nb_layers, min_distance, max_distance, dc.camera_fov, dc.camera_position, dc.camera_direction, dc.scene_info_file_name, dc.sun_orientations_file_name, dc.scene_gt_file_name, dc.camera_info_file_name)



if __name__ == "__main__":
    main()