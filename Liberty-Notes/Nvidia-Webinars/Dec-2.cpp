// INTRODUCTION TO PHYSICAL AI

/*
nvidia webinar
```
// (physical testing is expensive ... data is costly to capture... irl testing is also extremely dangerous and parts are expensive too)

- synthetic data generation is important... and recommended to highly specialise in
- nvidia omniverse + nvidia cosomos

- synthetic data for mobility <-- enable precise path planning and obstacle avoidance
- synthetic data for manipulation <-- enhancing dexterity and task execution in complex workflows



    Nvidia Isaac Sim
    - An open-source reference robotics simulation framework...
        - Can test code... can also connect hardware... there are ways to 
          connect Jetson into Issac Sim... robot thinks that it's getting real
          world input and outputs... but it's only inside the Sim!
        - Do try to dig into their github.

        - Lots of Features
          * SimReady Assests - Access over FOSS 1000 SimReady assets
            - cooker robot... factory workspace...
          * Robot Models
          * High-fidelity Physics Simulation
            - IRL things are permanent... bouncing screws, ... , etc.
          * Fully Extensible  
          * Synthetic Data Generation  
          * Instant GPU access with Brev

    Nvidia Issac Lab
    - Built on top of Issac Sim...
      - Shows that there's a lot of ways for robots to be trained or learned
      - Reinforcement learning... doing things at scale... not just one instance
        of the robots... but thousands of robots trying things concurrently, as
        if it's exponential...
      - Imitation Learning
    - Issac Lab key features
      - similar to Issac Sim... it's basically a gym for these robots... allow
        these models to be trained and be improved
        

train (synthetic data) -> simulate (irl testing is a lot more expensive in comparison) -> deploy
```
*/


// ---------- //                // ---------- //               // ---------- //
// ROBOT FOUNDATION MODELS AND ACCELERATED LIBRARIES

/*
    DEPLOYMENT 
    - Issac GROOT N1.5 Robot Foundation Model
    - VLA (Vision-Language-Action model)
        * They tend to have a dual-system architecture...
            1. Deep thinking brain <-- system 2
            1. Acting brain        <-- system 1 (actuation)
    - HF Link:
        * https://huggingface.co/docs/lerobot/en/groot
        * https://huggingface.co/blog/nvidia/gr00t-n1-5-so101-tuning


    - CAN ALSO POST TRAIN THESE MODELS?        



    NVIDIA Issac ROS (library)
    - Library used by most robotic company it seems
    - Motion Planning, Pose estimation (also hardware accelerated too)
    - 3D scene reconstruction, object detection, depth segmentation, visual SLAM

        * 



    NVIDIA Jetson
    - Physical AI demands Ultra-HPC
      * Humanoid Robotics (Multimodal AI)        
        - must be able to process through sensor fusion... cameras, lidar, etc.
        - and then also be able to reason through all of this...
      * Visual Agent (Custom)
      * ...

    - Platform: Jetson AGX Thor  


    Newton
     - Open source physics engine


    Robotics is multidisciplinary... 
*/





/*

    - TRY THE PROJECT REGARDING HF'S 100USD ROBOTIC ARM


    - Post Training with Nvidia Issac Groot N1.5 robot Foundation Model???
        - LeRobot SO-101 Arm
          - https://huggingface.co/blog/nvidia/gr00t-n1-5-so101-tuning


    - Nvidia Jetson AI Lab
        - Lots of ideas here and tutorials too!
            - https://www.jetson-ai-lab.com/
*/